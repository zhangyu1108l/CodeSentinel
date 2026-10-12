"""Deterministic analysis report builder (Phase 8.7).

The Reporter turns one finished analysis run (merged findings plus the
per stage execution facts) into the stable AnalysisReport structure. It
performs no LLM call and no I/O: every value is derived from what the
nodes actually produced.

Truthfulness rules:

- degraded is True as soon as any stage was incomplete: context
  unavailable or degraded, a failed agent node, a recoverable node
  error, a degraded static analysis stage or a failed validator.
- a degraded run that produced zero findings carries an explicit note, so
  an empty finding list is never presented as a clean result;
- static tool status and the validation summary are always included
  (safe counts and status codes only).
"""

from app.schemas.report import (
    AnalysisFinding,
    AnalysisReport,
    FindingSource,
    ReportStatus,
)
from app.schemas.review import (
    Category,
    ReviewFinding,
    ReviewTaskRequest,
    ReviewTaskResult,
    Severity,
)

NOTE_EMPTY_DEGRADED = (
    "no findings were reported because the analysis degraded; this is "
    "not a clean result"
)

MAPPING_MISSING_AGENT_FIELDS = "missing_agent_fields"


def build_analysis_report(
    *,
    request: ReviewTaskRequest,
    findings: list[AnalysisFinding],
    duplicates_merged: int = 0,
    source_counts: dict | None = None,
    planned_agents: list[Category] = (),
    executed_agents: list[Category] = (),
    failed_agents: list[Category] = (),
    skipped_agents: list[Category] = (),
    recoverable_errors: list[str] = (),
    context_report: dict | None = None,
    static_report: dict | None = None,
    validation_summary: dict | None = None,
) -> AnalysisReport:
    """Build the stable report of one analysis run."""
    context_degraded = bool(
        context_report is not None and context_report.get("degraded")
    )
    context_available = bool(
        context_report is not None and context_report.get("available")
    )
    static_degraded = bool(
        static_report is not None and static_report.get("degraded")
    )
    validation_failed = bool(
        validation_summary is not None
        and validation_summary.get("failed") is not None
    )

    degraded = (
        not context_available
        or context_degraded
        or bool(failed_agents)
        or bool(recoverable_errors)
        or static_degraded
        or validation_failed
    )

    notes = _build_notes(
        degraded=degraded,
        findings=findings,
        executed_agents=executed_agents,
        failed_agents=failed_agents,
        skipped_agents=skipped_agents,
        context_report=context_report,
        context_available=context_available,
        static_report=static_report,
        validation_summary=validation_summary,
        validation_failed=validation_failed,
    )

    severity_counts = {severity.value: 0 for severity in Severity}
    for finding in findings:
        severity_counts[finding.severity.value] += 1

    return AnalysisReport(
        task_id=request.task_id,
        repository=request.repository,
        pr_number=request.pr_number,
        commit_sha=request.commit_sha,
        status=ReportStatus.DEGRADED if degraded else ReportStatus.COMPLETED,
        degraded=degraded,
        findings=list(findings),
        finding_count=len(findings),
        severity_counts=severity_counts,
        source_counts=dict(source_counts or {}),
        duplicates_merged=duplicates_merged,
        planned_agents=list(planned_agents),
        executed_agents=list(executed_agents),
        failed_agents=list(failed_agents),
        skipped_agents=list(skipped_agents),
        recoverable_errors=list(recoverable_errors),
        context=dict(context_report) if context_report is not None else None,
        static_analysis=(
            dict(static_report) if static_report is not None else None
        ),
        validation=(
            dict(validation_summary)
            if validation_summary is not None
            else None
        ),
        notes=notes,
    )


def _build_notes(
    *,
    degraded: bool,
    findings: list[AnalysisFinding],
    executed_agents: list[Category],
    failed_agents: list[Category],
    skipped_agents: list[Category],
    context_report: dict | None,
    context_available: bool,
    static_report: dict | None,
    validation_summary: dict | None,
    validation_failed: bool,
) -> list[str]:
    notes: list[str] = []
    if degraded and not findings:
        notes.append(NOTE_EMPTY_DEGRADED)
    if not context_available:
        reason = (
            context_report.get("reason")
            if context_report is not None
            else None
        )
        notes.append(
            "PR context unavailable" + (f": {reason}" if reason else "")
        )
    if failed_agents:
        names = ", ".join(category.value for category in failed_agents)
        notes.append(f"agent node(s) failed: {names}")
    if skipped_agents:
        names = ", ".join(category.value for category in skipped_agents)
        notes.append(f"planned agent(s) skipped (no implementation): {names}")
    if static_report is None:
        notes.append("static analysis stage was not run")
    elif not static_report.get("available"):
        reason = static_report.get("reason")
        notes.append(
            "static analysis unavailable"
            + (f": {reason}" if reason else "")
        )
    if validation_failed:
        notes.append(
            "validator failed: "
            + str(validation_summary.get("failed"))
        )
    if validation_summary is not None:
        unverified = validation_summary.get("static_unverified") or 0
        if unverified:
            notes.append(
                f"{unverified} static finding(s) could not be verified "
                "against the bounded payload; kept as evidence"
            )
    if not executed_agents and not failed_agents and not skipped_agents:
        notes.append("no agent node was planned")
    return notes


def resolve_mapping_status(status: str, mapping_complete: bool) -> str:
    """Status after mapping, never improving the original one.

    An incomplete mapping (a finding that could not be represented as a
    ReviewFinding) marks a COMPLETED result as DEGRADED. DEGRADED stays
    DEGRADED and FAILED stays FAILED: a mapping gap must never overwrite
    or hide a more severe status. The task still completes normally; the
    worker retry path is reserved for exceptions and HTTP errors.
    """
    if mapping_complete or status != "COMPLETED":
        return status
    return "DEGRADED"


def to_review_task_result(report: AnalysisReport) -> ReviewTaskResult:
    """Map one AnalysisReport onto the production API contract.

    Explicit and lossless mapping rules (Phase 8.8):

    - Agent findings map 1:1 onto ReviewFinding. Their confidence, title,
      reason and suggestion are guaranteed non blank by the validator; a
      defensive missing field is NOT invented: the finding is recorded in
      report["mapping_issues"] (with safe metadata: file path, rule id,
      line range and the missing field names) and left out of findings.
    - Static only findings cannot become ReviewFinding without inventing
      confidence and description fields, so they are preserved as
      structured evidence in report["static_findings"] (tool, rule id,
      severity, category, message, path and line range); nothing is
      silently dropped.
    - The full AnalysisReport JSON is preserved under report["analysis"],
      so no information (sources, tool metadata, notes, stage summaries)
      is lost even when the legacy fields cannot carry it.
    - status follows Phase 8.9 decision A: an incomplete mapping marks a
      COMPLETED result as DEGRADED (DEGRADED and FAILED are never
      improved); the task still returns normally, so a mapping gap alone
      never triggers a worker retry. mapping_complete stays False and the
      problem details stay in mapping_issues / summary.
    """
    findings: list[ReviewFinding] = []
    static_evidence: list[dict] = []
    mapping_issues: list[dict] = []
    merged_static = 0

    for finding in report.findings:
        has_agent = FindingSource.AGENT in finding.sources
        has_static = FindingSource.STATIC in finding.sources
        if has_agent and has_static:
            merged_static += 1
        if not has_agent:
            static_evidence.append(_static_evidence_entry(finding))
            continue
        missing = _missing_agent_fields(finding)
        if missing:
            mapping_issues.append(
                {
                    "reason": MAPPING_MISSING_AGENT_FIELDS,
                    "fields": missing,
                    "file_path": finding.file_path,
                    "rule_id": finding.rule_id,
                    "start_line": finding.start_line,
                    "end_line": finding.end_line,
                }
            )
            continue
        findings.append(
            ReviewFinding(
                category=finding.category,
                severity=finding.severity,
                confidence=finding.confidence,
                rule_id=finding.rule_id,
                title=finding.title,
                file_path=finding.file_path,
                start_line=finding.start_line,
                end_line=finding.end_line,
                description=finding.message,
                reason=finding.reason,
                suggestion=finding.suggestion,
                references=list(finding.references),
            )
        )

    mapping_complete = not mapping_issues
    status = resolve_mapping_status(report.status.value, mapping_complete)
    summary = (
        f"Analysis {status.lower()} for "
        f"{report.repository}#{report.pr_number}: "
        f"{len(findings)} finding(s) reported."
    )
    if report.degraded:
        summary += (
            " Analysis degraded; incomplete stages are recorded in the "
            "report."
        )
    if mapping_issues:
        summary += (
            f" {len(mapping_issues)} finding(s) could not be mapped and "
            "are recorded in report.mapping_issues; the result is marked "
            "DEGRADED because it is incomplete."
        )

    payload = {
        "summary": summary,
        "total_findings": len(findings),
        "degraded": report.degraded or not mapping_complete,
        "status": status,
        "mapping_complete": mapping_complete,
        "mapping_issues": mapping_issues,
        "analysis": report.model_dump(mode="json"),
        "severity_counts": dict(report.severity_counts),
        "source_counts": dict(report.source_counts),
        "static_evidence_merged": merged_static,
        "static_findings": static_evidence,
        "static_finding_count": len(static_evidence),
        "duplicates_merged": report.duplicates_merged,
        "agents": {
            "planned": [
                category.value for category in report.planned_agents
            ],
            "executed": [
                category.value for category in report.executed_agents
            ],
            "failed": [
                category.value for category in report.failed_agents
            ],
            "skipped": [
                category.value for category in report.skipped_agents
            ],
            "recoverable_errors": list(report.recoverable_errors),
        },
        "context": report.context,
        "static_analysis": report.static_analysis,
        "validation": report.validation,
        "notes": list(report.notes),
    }
    return ReviewTaskResult(
        task_id=report.task_id,
        status=status,
        report=payload,
        findings=findings,
    )


def _missing_agent_fields(finding: AnalysisFinding) -> list[str]:
    """Field names that a ReviewFinding requires but this one lacks."""
    missing: list[str] = []
    for name, value in (
        ("confidence", finding.confidence),
        ("title", finding.title),
        ("reason", finding.reason),
        ("suggestion", finding.suggestion),
    ):
        if value is None or (
            isinstance(value, str) and not value.strip()
        ):
            missing.append(name)
    return missing


def _static_evidence_entry(finding: AnalysisFinding) -> dict:
    return {
        "tool": finding.tool.value if finding.tool is not None else None,
        "rule_id": finding.rule_id,
        "category": finding.category.value,
        "severity": finding.severity.value,
        "message": finding.message,
        "file_path": finding.file_path,
        "start_line": finding.start_line,
        "end_line": finding.end_line,
        "sources": [source.value for source in finding.sources],
    }