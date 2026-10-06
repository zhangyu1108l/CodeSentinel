import logging

from app.llm.llm_service import LLMService
from app.prompts.review import build_messages
from app.schemas.review import ReviewTaskRequest, ReviewTaskResult

logger = logging.getLogger("codesentinel-ai.review_service")


class ReviewService:
    """Review orchestration: prompt assembly -> LLM analysis -> result.

    Phase 5.2: findings come from the real DeepSeek LLM via LLMService.
    LLM failures propagate to the caller (FastAPI -> worker -> Phase 4
    retry chain); no internal retry at this stage.
    """

    def __init__(self, llm_service: LLMService = None):
        self.llm_service = llm_service or LLMService()

    async def review(self, request: ReviewTaskRequest) -> ReviewTaskResult:
        logger.info(
            "Reviewing task %d: repository=%s, pr=%d, sha=%s",
            request.task_id,
            request.repository,
            request.pr_number,
            request.commit_sha,
        )

        messages = build_messages(request)
        findings = await self.llm_service.generate_findings(messages)

        result = ReviewTaskResult(
            task_id=request.task_id,
            status="COMPLETED",
            report={
                "summary": "Review completed for "
                f"{request.repository}#{request.pr_number}.",
                "total_findings": len(findings),
            },
            findings=findings,
        )

        logger.info(
            "Review completed for task %d: status=%s, findings=%d",
            result.task_id,
            result.status,
            len(result.findings),
        )
        return result
