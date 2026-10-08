"""Review orchestration (Phase 5.2 + Phase 6.7.4 wiring + Phase 6.7.5 prompt).

Flow:

    PrContextClient.fetch(task_id) -> PrContext
        -> CodeContextBuilder.build -> CodeContext
        -> Phase 6.6 context budget applied to its files
        -> prompt assembly with the rendered CodeContext (Phase 6.7.5)
        -> LLM analysis (unchanged)

Context failures never raise: they degrade the review (status DEGRADED
plus a reason in report.context) and the prompt states that the PR
context is unavailable, so the Phase 4 retry chain stays reserved for
real review failures such as LLM errors, which keep propagating
unchanged. When no context client is configured the Phase 5 prompt is
kept as is.
"""

import logging

import httpx

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

logger = logging.getLogger("codesentinel-ai.review_service")

STATUS_COMPLETED = "COMPLETED"
STATUS_DEGRADED = "DEGRADED"
REASON_NOT_CONFIGURED = "not_configured"


class ReviewService:
    """Review orchestration: context loading -> prompt -> LLM -> result.

    pr_context_client may be None, in which case context loading is
    disabled and the Phase 5 behaviour is kept (status COMPLETED, report
    context marked not_configured). context_budget defaults to the Phase
    6.6 DEFAULT_BUDGET; passing None uses that default.
    """

    def __init__(
        self,
        llm_service: LLMService = None,
        pr_context_client: PrContextClient = None,
        context_builder: CodeContextBuilder = None,
        context_budget: ContextBudget = None,
    ):
        self.llm_service = llm_service or LLMService()
        self.pr_context_client = pr_context_client
        self.context_builder = context_builder or CodeContextBuilder()
        self.context_budget = context_budget

    async def review(self, request: ReviewTaskRequest) -> ReviewTaskResult:
        logger.info(
            "Reviewing task %d: repository=%s, pr=%d, sha=%s",
            request.task_id,
            request.repository,
            request.pr_number,
            request.commit_sha,
        )

        context, context_report = await self._load_context(request)

        messages = build_messages(
            request, context=context, context_report=context_report
        )
        logger.debug(
            "Review prompt built for task %d: messages=%d, chars=%d",
            request.task_id,
            len(messages),
            sum(len(message["content"]) for message in messages),
        )
        findings = await self.llm_service.generate_findings(messages)

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

        result = ReviewTaskResult(
            task_id=request.task_id,
            status=STATUS_DEGRADED if degraded else STATUS_COMPLETED,
            report={
                "summary": summary,
                "total_findings": len(findings),
                "context": context_report,
            },
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
        self, request: ReviewTaskRequest
    ) -> tuple[CodeContext | None, dict]:
        """Fetch, assemble and budget the PR context, or degrade.

        Returns the assembled CodeContext (or None when unavailable) and
        the report status dict. Every failure inside this boundary
        degrades the review instead of raising: a context problem must not
        enter the Phase 4 retry chain, because retrying cannot repair a
        404, a contract mismatch or a network error. The reason is logged
        (WARNING) and recorded in the report; the exception detail is kept
        at DEBUG only.
        """
        if self.pr_context_client is None:
            return None, {
                "available": False,
                "degraded": False,
                "reason": REASON_NOT_CONFIGURED,
            }

        try:
            pr_context = await self.pr_context_client.fetch(request.task_id)
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


def _failure_reason(error: Exception) -> str:
    """Short, log safe reason code for a degraded context.

    Exception messages can embed source content (validators echo input),
    so only the failure class and, for HTTP failures, the status code are
    exposed.
    """
    if isinstance(error, httpx.HTTPStatusError):
        return f"http_error:{error.response.status_code}"
    return type(error).__name__