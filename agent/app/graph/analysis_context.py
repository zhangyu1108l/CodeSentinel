"""Analysis context stage for the multi agent pipeline (Phase 8.7).

Loads the PR context, applies the Phase 6.6 context budget, runs the
Phase 8.6 static analysis stage on the fetched content and builds the
Phase 8.4 bounded agent payload. It is the context node of the analysis
workflow and reuses the existing components end to end
(PrContextClient -> CodeContextBuilder -> context budget ->
StaticAnalysisService -> build_agent_context); no component is
reimplemented here.

Budget rules:

- the context fetch is capped by both the local context timeout and the
  remaining shared budget, exactly like the production review path;
- the static analysis stage receives the same RequestBudget instance and
  applies its own share policy (at most half of the remaining budget,
  split across tools), so its cost is paid from the shared deadline;
- every failure degrades the stage result explicitly (reason code only);
  nothing raises for context or tool level problems and no finding is
  fabricated. Source content is only passed to the workspace, never
  logged.
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field

import httpx

from app.agents.context_payload import (
    AgentContextPayload,
    build_agent_context,
)
from app.config.settings import settings
from app.context.code_context_builder import CodeContextBuilder
from app.context.context_size_controller import (
    DEFAULT_BUDGET,
    aggregate_stats,
    aggregate_truncation,
    apply_context_budget_to_files,
)
from app.context.pr_context_client import PrContextClient
from app.schemas.code_context import CodeContext, ContextBudget
from app.schemas.review import ReviewTaskRequest
from app.schemas.static_analysis import StaticAnalysisFinding
from app.services.request_budget import RequestBudget
from app.services.static_analysis_service import StaticAnalysisService

logger = logging.getLogger("codesentinel-ai.analysis_context")

REASON_NOT_CONFIGURED = "not_configured"
REASON_BUDGET_EXHAUSTED = "budget_exhausted"
REASON_CONTEXT_UNAVAILABLE = "context_unavailable"
REASON_NO_FILES = "no_files"


@dataclass(frozen=True)
class ContextStageResult:
    """Everything the analysis nodes need from the context stage."""

    payload: AgentContextPayload | None
    context_report: dict
    static_report: dict
    static_findings: list[StaticAnalysisFinding] = field(
        default_factory=list
    )
    changed_ranges: dict[str, list[tuple[int, int]]] = field(
        default_factory=dict
    )


class AnalysisContextStage:
    """Fetch, budget and analyse the PR context for one analysis run."""

    def __init__(
        self,
        pr_context_client: PrContextClient = None,
        context_builder: CodeContextBuilder = None,
        context_budget: ContextBudget = None,
        static_analysis_service: StaticAnalysisService = None,
        context_timeout_seconds: float = None,
    ):
        self.pr_context_client = pr_context_client
        self.context_builder = context_builder or CodeContextBuilder()
        self.context_budget = context_budget
        self.static_analysis_service = static_analysis_service
        self._context_timeout_seconds = _positive_seconds(
            (
                settings.PR_CONTEXT_TIMEOUT
                if context_timeout_seconds is None
                else context_timeout_seconds
            ),
            "context_timeout_seconds",
        )

    async def prepare(
        self, request: ReviewTaskRequest, budget: RequestBudget
    ) -> ContextStageResult:
        """Run the whole context stage once, degrading on every failure."""
        if self.pr_context_client is None:
            return ContextStageResult(
                payload=None,
                context_report=_context_report(
                    available=False,
                    degraded=False,
                    reason=REASON_NOT_CONFIGURED,
                ),
                static_report=_static_unavailable(REASON_NOT_CONFIGURED),
            )
        if budget.expired():
            return ContextStageResult(
                payload=None,
                context_report=_context_report(
                    available=False,
                    degraded=True,
                    reason=REASON_BUDGET_EXHAUSTED,
                ),
                static_report=_static_unavailable(
                    REASON_BUDGET_EXHAUSTED, degraded=True
                ),
            )

        try:
            async with asyncio.timeout(
                budget.limit(self._context_timeout_seconds)
            ):
                pr_context = await self.pr_context_client.fetch(
                    request.task_id
                )
            code_context = self._build_context(pr_context)
            summary = _context_summary(code_context)
        except Exception as error:
            reason = _failure_reason(error)
            logger.warning(
                "Analysis context unavailable for task %d (reason=%s)",
                request.task_id,
                reason,
            )
            return ContextStageResult(
                payload=None,
                context_report=_context_report(
                    available=False,
                    degraded=True,
                    reason=reason,
                ),
                static_report=_static_unavailable(
                    REASON_CONTEXT_UNAVAILABLE, degraded=True
                ),
            )

        static_report, static_findings = await self._run_static(
            request, code_context, budget
        )
        payload = build_agent_context(
            code_context, static_findings=static_findings
        )
        logger.info(
            "Analysis context ready for task %d: files=%d, "
            "withContent=%d, payloadAvailable=%s, staticTools=%d",
            request.task_id,
            summary["file_count"],
            summary["files_with_content"],
            payload.available,
            len(static_report.get("tools_run", [])),
        )
        return ContextStageResult(
            payload=payload,
            context_report=summary,
            static_report=static_report,
            static_findings=static_findings,
            changed_ranges=_changed_ranges(code_context),
        )

    def _build_context(self, pr_context) -> CodeContext:
        context = self.context_builder.build(pr_context)
        budget = (
            self.context_budget
            if self.context_budget is not None
            else DEFAULT_BUDGET
        )
        files = apply_context_budget_to_files(context.files, budget)
        return context.model_copy(
            update={
                "files": files,
                "stats": aggregate_stats(files),
                "truncation": aggregate_truncation(files),
            }
        )

    async def _run_static(
        self,
        request: ReviewTaskRequest,
        code_context: CodeContext,
        budget: RequestBudget,
    ) -> tuple[dict, list[StaticAnalysisFinding]]:
        """Run the static stage on the fetched content, or explain why not.

        The report shape mirrors ReviewService: available / degraded /
        reason plus the safe tool summary; a missing executable or a
        timeout keeps its explicit non OK status and never becomes a
        successful empty scan.
        """
        if self.static_analysis_service is None:
            return _static_unavailable(REASON_NOT_CONFIGURED), []

        files = _collect_content_files(code_context)
        if not files:
            return _static_unavailable(REASON_NO_FILES), []

        try:
            outcome = await asyncio.to_thread(
                self.static_analysis_service.analyze, files, budget
            )
        except Exception as error:
            reason = type(error).__name__
            logger.warning(
                "Static analysis unavailable for task %d (reason=%s)",
                request.task_id,
                reason,
            )
            return _static_unavailable(reason, degraded=True), []

        report = {
            "available": bool(outcome.results),
            "degraded": outcome.degraded,
            "reason": (
                None
                if outcome.results
                else (
                    outcome.notes[0]
                    if outcome.notes
                    else "no_tool_results"
                )
            ),
        }
        report.update(outcome.report_summary())
        return report, outcome.findings


def _collect_content_files(code_context: CodeContext) -> dict[str, str]:
    """Text content of the context files, exactly as fetched."""
    return {
        file_context.file_diff.path: file_context.content.content
        for file_context in code_context.files
        if file_context.content_available
        and file_context.content is not None
        and file_context.content.content is not None
    }


def _changed_ranges(
    code_context: CodeContext,
) -> dict[str, list[tuple[int, int]]]:
    """Head revision changed-line ranges per file (diff evidence)."""
    ranges: dict[str, list[tuple[int, int]]] = {}
    for file_context in code_context.files:
        changed = [
            (item.start_line, item.end_line)
            for item in file_context.file_diff.changed_ranges
        ]
        if changed:
            ranges[file_context.file_diff.path] = changed
    return ranges


def _context_report(available: bool, degraded: bool, reason: str) -> dict:
    return {
        "available": available,
        "degraded": degraded,
        "reason": reason,
        "file_count": 0,
        "files_with_content": 0,
        "estimated_tokens": 0,
        "truncated": False,
    }


def _context_summary(context: CodeContext) -> dict:
    stats = context.stats
    return {
        "available": True,
        "degraded": False,
        "reason": None,
        "file_count": len(context.files),
        "files_with_content": sum(
            1
            for file_context in context.files
            if file_context.content_available
        ),
        "estimated_tokens": (
            stats.estimated_tokens if stats is not None else 0
        ),
        "truncated": bool(
            context.truncation is not None
            and context.truncation.applied
        ),
    }


def _static_unavailable(reason: str, degraded: bool = False) -> dict:
    return {
        "available": False,
        "degraded": degraded,
        "reason": reason,
        "tools_run": [],
        "findings": 0,
    }


def _failure_reason(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return f"http_error:{error.response.status_code}"
    return type(error).__name__


def _positive_seconds(value: float, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{name} must be a positive finite number")
    return float(value)


def context_report_unavailable(reason: str, degraded: bool) -> dict:
    """Safe degraded context report for callers outside this stage."""
    return _context_report(
        available=False, degraded=degraded, reason=reason
    )


def static_report_unavailable(
    reason: str, degraded: bool = False
) -> dict:
    """Safe unavailable static report for callers outside this stage."""
    return _static_unavailable(reason, degraded=degraded)