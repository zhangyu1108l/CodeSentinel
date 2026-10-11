import logging

import httpx
from pydantic import ValidationError

from app.config.settings import settings
from app.schemas.review import ReviewTaskRequest, ReviewTaskResult
from app.schemas.validation import validation_error_summary

logger = logging.getLogger("codesentinel-ai.ai_client")


class AiServiceResponseError(Exception):
    """The AI service returned a review result that violates the schema.

    Raised instead of re-raising the raw Pydantic ValidationError, whose
    message embeds a preview of the response (which can contain findings
    text). The generic message keeps the worker failure path stable.
    """


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
        except httpx.HTTPStatusError as error:
            logger.error(
                "Failed to request review for task %d from AI service: "
                "http_status=%s",
                request.task_id,
                error.response.status_code,
            )
            raise
        except ValidationError as error:
            logger.error(
                "Failed to request review for task %d from AI service: "
                "invalid response schema (%s)",
                request.task_id,
                validation_error_summary(error),
            )
            raise AiServiceResponseError(
                "AI service returned an invalid review result"
            ) from None
        except Exception as error:
            logger.error(
                "Failed to request review for task %d from AI service: %s",
                request.task_id,
                type(error).__name__,
            )
            raise
