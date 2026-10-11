"""Review orchestration (Phase 5.2 + Phase 6.7.4 wiring + Phase 8.6 static stage).

Flow:

    PrContextClient.fetch(task_id) -> PrContext
        -> CodeContextBuilder.build -> CodeContext
        -> Phase 6.6 context budget applied to its files
        -> static analysis stage (Phase 8.6, optional; shared budget)
        -> prompt assembly with the rendered CodeContext and the static
           evidence (Phase 6.7.5 + Phase 8.6)
        -> LLM analysis (unchanged)

Context and static analysis failures never raise: they degrade the review
(status DEGRADED plus a reason in report.context / report.static_analysis)
and the prompt states what evidence is missing, so the Phase 4 retry chain
stays reserved for real review failures such as LLM errors, which keep
propagating unchanged. When no context client is configured the Phase 5
prompt is kept as is; when no static analysis service is configured the
report keeps its pre Phase 8.6 shape.

Every review also runs under one total request budget (Phase 8 timeout
governance): the context fetch is capped by both the local PR context
timeout and the remaining budget, and the LLM call may only use what the
budget has left. Running out of budget before or during the LLM call
raises ReviewBudgetExceededError, so an unfinished review can never be
reported as a success.
"""

import asyncio
import logging
import math

import httpx
from pydantic import ValidationError

from app.config.settings import settings
from app.context.code_context_builder import CodeContextBuilder
from app.context.context_size_controller import (
    DEFAULT_BUDGET,
    aggregate_stats,
    aggregate_truncation,
    apply_context_budget_to_files,
)
from app.context.pr_context_client import PrContextClient
from app.llm.llm_service import LLMService
from app.prompts.review import build_messages
from app.schemas.code_context import CodeContext, ContextBudget
from app.schemas.review import ReviewTaskRequest, ReviewTaskResult
from app.schemas.static_analysis import (
    StaticAnalysisFinding,
    StaticAnalysisStatus,
)
from app.schemas.validation import validation_error_summary
from app.services.request_budget import (
    RequestBudget,
    ReviewBudgetExceededError,
)
from app.services.static_analysis_service import StaticAnalysisService

logger = logging.getLogger("codesentinel-ai.review_service")

STATUS_COMPLETED = "COMPLETED"
STATUS_DEGRADED = "DEGRADED"
REASON_NOT_CONFIGURED = "not_configured"
REASON_BUDGET_EXHAUSTED = "budget_exhausted"
REASON_CONTEXT_UNAVAILABLE = "context_unavailable"
REASON_NO_FILES = "no_files"
REASON_NO_TOOL_RESULTS = "no_tool_results"


class ReviewService:
    """Review orchestration: context loading -> prompt -> LLM -> result.

    pr_context_client may be None, in which case context loading is
    disabled and the Phase 5 behaviour is kept (status COMPLETED, report
    context marked not_configured). context_budget defaults to the Phase
    6.6 DEFAULT_BUDGET; passing None uses that default. request_budget
    seconds defaults to settings.REVIEW_TOTAL_BUDGET and
    context_timeout_seconds to settings.PR_CONTEXT_TIMEOUT; both may be
    injected for tests. review() also accepts an optional RequestBudget:
    a graph workflow injects its shared budget so every node uses the
    remaining time of one review instead of a fresh deadline.

    static_analysis_service may be None (default), in which case no
    static analysis runs and the report keeps its previous shape. When a
    service is injected (production wiring), the stage runs inside the
    same shared budget and the report gains a "static_analysis" entry;
    the stage is fully degradable and never turns a tool failure into a
    successful empty scan.
    """

    def __init__(
        self,
        llm_service: LLMService = None,
        pr_context_client: PrContextClient = None,
        context_builder: CodeContextBuilder = None,
        context_budget: ContextBudget = None,
        request_budget_seconds: float = None,
        context_timeout_seconds: float = None,
        static_analysis_service: StaticAnalysisService = None,
    ):
        self.llm_service = llm_service or LLMService()
        self.pr_context_client = pr_context_client
        self.context_builder = context_builder or CodeContextBuilder()
        self.context_budget = context_budget
        self._request_budget_seconds = _positive_seconds(
            (
                settings.REVIEW_TOTAL_BUDGET
                if request_budget_seconds is None
                else request_budget_seconds
            ),
            "request_budget_seconds",
        )
        self._context_timeout_seconds = _positive_seconds(
            (
                settings.PR_CONTEXT_TIMEOUT
                if context_timeout_seconds is None
                else context_timeout_seconds
            ),
            "context_timeout_seconds",
        )
        self.static_analysis_service = static_analysis_service

    async def review(
        self,
        request: ReviewTaskRequest,
        budget: RequestBudget = None,
    ) -> ReviewTaskResult:
        logger.info(
            "Reviewing task %d: repository=%s, pr=%d, sha=%s",
            request.task_id,
            request.repository,
            request.pr_number,
            request.commit_sha,
        )

        if budget is None:
            budget = RequestBudget(self._request_budget_seconds)
        context, context_report = await self._load_context(request, budget)

        static_findings: list[StaticAnalysisFinding] = []
        static_report: dict | None = None
        if self.static_analysis_service is not None:
            static_findings, static_report = await self._run_static_analysis(
                request, context, budget
            )

        messages = build_messages(
            request,
            context=context,
            context_report=context_report,
            static_findings=static_findings,
        )
        logger.debug(
            "Review prompt built for task %d: messages=%d, chars=%d",
            request.task_id,
            len(messages),
            sum(len(message["content"]) for message in messages),
        )

        logger.debug(
            "Review budget for task %d: total=%.1fs remaining=%.3fs",
            request.task_id,
            budget.seconds,
            budget.remaining(),
        )
        if budget.expired():
            raise ReviewBudgetExceededError(
                "Review budget of "
                f"{budget.seconds:g}s exhausted before LLM analysis "
                f"(task {request.task_id})"
            )
        try:
            async with asyncio.timeout(budget.remaining()):
                findings = await self.llm_service.generate_findings(
                    messages
                )
        except TimeoutError as error:
            if budget.expired():
                raise ReviewBudgetExceededError(
                    "Review budget of "
                    f"{budget.seconds:g}s exhausted during LLM analysis "
                    f"(task {request.task_id})"
                ) from error
            raise

        degraded = context_report["degraded"]
        if degraded:
            summary = (
                "Review degraded for "
                f"{request.repository}#{request.pr_number}: "
                "PR context unavailable."
            )
        else:
            summary = (
                "Review completed for "
                f"{request.repository}#{request.pr_number}."
            )

        report = {
            "summary": summary,
            "total_findings": len(findings),
            "context": context_report,
        }
        if static_report is not None:
            report["static_analysis"] = static_report

        result = ReviewTaskResult(
            task_id=request.task_id,
            status=STATUS_DEGRADED if degraded else STATUS_COMPLETED,
            report=report,
            findings=findings,
        )

        logger.info(
            "Review finished for task %d: status=%s, findings=%d, "
            "contextAvailable=%s",
            result.task_id,
            result.status,
            len(result.findings),
            context_report["available"],
        )
        return result

    async def _load_context(
        self, request: ReviewTaskRequest, budget: RequestBudget
    ) -> tuple[CodeContext | None, dict]:
        """Fetch, assemble and budget the PR context, or degrade.

        Returns the assembled CodeContext (or None when unavailable) and
        the report status dict. Every failure inside this boundary
        degrades the review instead of raising: a context problem must not
        enter the Phase 4 retry chain, because retrying cannot repair a
        404, a contract mismatch or a network error. The reason is logged
        (WARNING) and recorded in the report; the exception detail is kept
        at DEBUG only.

        The fetch is capped by both the local PR context timeout and the
        remaining request budget, so a slow context stage can never use up
        more than its share; a timeout here degrades like any other
        context failure.
        """
        if self.pr_context_client is None:
            return None, {
                "available": False,
                "degraded": False,
                "reason": REASON_NOT_CONFIGURED,
            }
        if budget.expired():
            logger.warning(
                "PR context skipped for task %d: request budget exhausted",
                request.task_id,
            )
            return None, {
                "available": False,
                "degraded": True,
                "reason": REASON_BUDGET_EXHAUSTED,
            }

        try:
            async with asyncio.timeout(
                budget.limit(self._context_timeout_seconds)
            ):
                pr_context = await self.pr_context_client.fetch(
                    request.task_id
                )
            context = self.context_builder.build(pr_context)
            context = self._apply_context_budget(context)
            summary = self._context_summary(context)
        except Exception as error:
            reason = _failure_reason(error)
            logger.warning(
                "PR context unavailable for task %d; review degrades "
                "(reason=%s)",
                request.task_id,
                reason,
            )
            if isinstance(error, ValidationError):
                logger.debug(
                    "PR context schema failure for task %d: %s",
                    request.task_id,
                    validation_error_summary(error),
                )
            else:
                logger.debug(
                    "PR context failure detail for task %d",
                    request.task_id,
                    exc_info=True,
                )
            return None, {
                "available": False,
                "degraded": True,
                "reason": reason,
            }

        logger.info(
            "PR context ready for task %d: files=%d, withContent=%d, "
            "estimatedTokens=%d, truncated=%s",
            request.task_id,
            summary["file_count"],
            summary["files_with_content"],
            summary["estimated_tokens"],
            summary["truncated"],
        )
        return context, summary

    async def _run_static_analysis(
        self,
        request: ReviewTaskRequest,
        context: CodeContext | None,
        budget: RequestBudget,
    ) -> tuple[list[StaticAnalysisFinding], dict]:
        """Run the static analysis stage inside the shared budget.

        The stage is a degradable sub-step like context loading: it never
        raises into the review. Tool level failures already stay inside
        the adapters as explicit non OK results; anything unexpected
        (caller defect, broken service) degrades to an empty evidence
        list recorded by class name only.

        The service receives the same RequestBudget instance as the rest
        of the review and may only use its share of the remaining time;
        the LLM stage then uses what is left. Source content only flows
        into the materialized workspace, never into logs.
        """
        if context is None:
            return [], _static_skipped(REASON_CONTEXT_UNAVAILABLE)

        files = {
            file_context.file_diff.path: file_context.content.content
            for file_context in context.files
            if file_context.content_available
            and file_context.content is not None
            and file_context.content.content is not None
        }
        if not files:
            return [], _static_skipped(REASON_NO_FILES)

        try:
            outcome = await asyncio.to_thread(
                self.static_analysis_service.analyze, files, budget
            )
        except Exception as error:
            reason = type(error).__name__
            logger.warning(
                "Static analysis unavailable for task %d; review "
                "continues without tool evidence (reason=%s)",
                request.task_id,
                reason,
            )
            logger.debug(
                "Static analysis failure detail for task %d",
                request.task_id,
                exc_info=True,
            )
            return [], _static_skipped(reason, degraded=True)

        report = {
            "available": bool(outcome.results),
            "degraded": outcome.degraded,
            "reason": (
                None
                if outcome.results
                else (
                    outcome.notes[0]
                    if outcome.notes
                    else REASON_NO_TOOL_RESULTS
                )
            ),
        }
        report.update(outcome.report_summary())
        logger.info(
            "Static analysis for task %d: tools_run=%d, findings=%d, "
            "degraded=%s",
            request.task_id,
            len(outcome.results),
            outcome.aggregate.finding_count,
            outcome.degraded,
        )
        return outcome.findings, report

    def _apply_context_budget(self, context: CodeContext) -> CodeContext:
        """Apply the Phase 6.6 budget to the assembled context files."""
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

    @staticmethod
    def _context_summary(context: CodeContext) -> dict:
        stats = context.stats
        return {
            "available": True,
            "degraded": False,
            "reason": None,
            "file_count": len(context.files),
            "files_with_content": sum(
                1 for file_context in context.files
                if file_context.content_available
            ),
            "estimated_tokens": (
                stats.estimated_tokens if stats is not None else 0
            ),
            "truncated": bool(
                context.truncation is not None and context.truncation.applied
            ),
        }


def _static_skipped(reason: str, degraded: bool = False) -> dict:
    """Report entry for a static stage that never started a tool.

    The shape mirrors a completed stage (available/degraded/reason plus
    all summary keys at their empty values) so consumers can read it
    uniformly; no result is fabricated and no scan is claimed.
    """
    return {
        "available": False,
        "degraded": degraded,
        "reason": reason,
        "tools_run": [],
        "status_counts": {
            status.value: 0 for status in StaticAnalysisStatus
        },
        "findings": 0,
        "completed_tools": [],
        "failed_tools": [],
        "skipped_tools": [],
        "budget_exhausted_tools": [],
        "not_configured_tools": [],
        "budget_exhausted": False,
    }


def _failure_reason(error: Exception) -> str:
    """Short, log safe reason code for a degraded context.

    Exception messages can embed source content (validators echo input),
    so only the failure class and, for HTTP failures, the status code are
    exposed.
    """
    if isinstance(error, httpx.HTTPStatusError):
        return f"http_error:{error.response.status_code}"
    return type(error).__name__


def _positive_seconds(value: float, name: str) -> float:
    """Validate a positive finite timeout from settings or a test."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError(f"{name} must be a positive finite number")
    return float(value)