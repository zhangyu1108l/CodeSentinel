"""Result aggregation for scheduled static analysis (Phase 8 prep).

Turns one SchedulerOutcome into a single deterministic summary: the
per-tool results in execution order, the flattened findings of the tools
that completed successfully, fixed status counts, and the split between
completed and failed tools.

Truthfulness rules:

- Findings are only ever taken from results whose status is OK. The Phase
  7.1 contract already forbids findings on any other status, and the
  aggregator does not relax it.
- Every non OK status (UNAVAILABLE, TIMEOUT, ERROR, PARSE_ERROR) counts as
  failed for completion purposes: a tool that did not complete cannot be
  counted as a successful analysis.
- Tools skipped because no target file applied to them are reported
  separately and are not failures. Tools that were never started because
  the optional batch budget was used up are reported separately too: they
  are not failures, but the analysis is incomplete, so partial becomes
  True as soon as any tool failed or was budget exhausted.

The aggregator performs no deduplication, no severity or confidence
recalculation and no LLM verification: those are later pipeline stages.
"""

from pydantic import BaseModel, Field

from app.analyzers.scheduler import SchedulerOutcome
from app.schemas.static_analysis import (
    StaticAnalysisFinding,
    StaticAnalysisResult,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)


class StaticAnalysisAggregate(BaseModel):
    """Deterministic summary of one scheduled static analysis batch.

    results keeps execution order, findings flattens the findings of OK
    results in the same order, status_counts always contains every status
    (zero included, in enum definition order), completed_tools lists the
    OK tools, failed_tools lists every non OK tool, skipped_tools are
    tools with no applicable target files, budget_exhausted_tools are
    applicable tools the batch budget never allowed to start, and partial
    is True as soon as any tool failed or was not started due to the
    budget.
    """

    results: list[StaticAnalysisResult] = Field(default_factory=list)
    skipped_tools: list[StaticAnalysisTool] = Field(default_factory=list)
    budget_exhausted_tools: list[StaticAnalysisTool] = Field(
        default_factory=list
    )
    findings: list[StaticAnalysisFinding] = Field(default_factory=list)
    finding_count: int = Field(default=0, ge=0)
    status_counts: dict[str, int] = Field(default_factory=dict)
    completed_tools: list[StaticAnalysisTool] = Field(
        default_factory=list
    )
    failed_tools: list[StaticAnalysisTool] = Field(default_factory=list)
    partial: bool = False


def aggregate_results(outcome: SchedulerOutcome) -> StaticAnalysisAggregate:
    """Aggregate one scheduler outcome without changing its meaning."""
    if not isinstance(outcome, SchedulerOutcome):
        raise ValueError("outcome must be a SchedulerOutcome")

    counts = {status.value: 0 for status in StaticAnalysisStatus}
    findings: list[StaticAnalysisFinding] = []
    completed: list[StaticAnalysisTool] = []
    failed: list[StaticAnalysisTool] = []
    for result in outcome.results:
        counts[result.status.value] += 1
        if result.status is StaticAnalysisStatus.OK:
            completed.append(result.tool)
            findings.extend(result.findings)
        else:
            failed.append(result.tool)

    exhausted = list(outcome.budget_exhausted_tools)
    return StaticAnalysisAggregate(
        results=list(outcome.results),
        skipped_tools=list(outcome.skipped_tools),
        budget_exhausted_tools=exhausted,
        findings=findings,
        finding_count=len(findings),
        status_counts=counts,
        completed_tools=completed,
        failed_tools=failed,
        partial=bool(failed) or bool(exhausted),
    )