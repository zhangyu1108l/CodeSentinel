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
    ReportStatus,
)
from app.schemas.review import (
    Category,
    ReviewTaskRequest,
    Severity,
)

NOTE_EMPTY_DEGRADED = (
    "no findings were reported because the analysis degraded; this is "
    "not a clean result"
)


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
    if not executed_agents and not failed_agents and not skipped_agents:
        notes.append("no agent node was planned")
    return notes