import logging

import httpx

from app.config.settings import settings
from app.schemas.review import ReviewTaskRequest, ReviewTaskResult

logger = logging.getLogger("codesentinel-ai.ai_client")


class AiServiceClient:
    def __init__(
        self,
        base_url: str = settings.AI_SERVICE_URL,
        timeout: float = settings.AI_SERVICE_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def review(self, request: ReviewTaskRequest) -> ReviewTaskResult:
        url = f"{self.base_url}/api/reviews"
        try:
            resp = httpx.post(
                url, json=request.model_dump(), timeout=self.timeout
            )
            resp.raise_for_status()
            result = ReviewTaskResult.model_validate(resp.json())
            logger.info(
                "Task %d review completed: status=%s, findings=%d",
                result.task_id,
                result.status,
                len(result.findings),
            )
            return result
        except Exception as e:
            logger.error(
                "Failed to request review for task %d from AI service: %s",
                request.task_id,
                e,
            )
            raise
