"""HTTP client for the Java PR context endpoint (Phase 6.7.2).

Fetches GET /api/tasks/{taskId}/pr-context and validates the response
against the PrContext DTO. Transport only: no context assembly, no prompt
building and no business decisions live here. Non 2xx responses, malformed
bodies and schema violations are logged and re-raised, matching the
existing service clients (AiServiceClient / JavaServiceClient). File
content is never written to logs.
"""

import logging

import httpx
from pydantic import ValidationError

from app.config.settings import settings
from app.schemas.pr_context import PrContext
from app.schemas.validation import validation_error_summary

logger = logging.getLogger("codesentinel-ai.pr_context_client")


class PrContextClient:
    """Fetches the PR context contract from the Spring Boot service."""

    def __init__(
        self,
        base_url: str = settings.JAVA_SERVICE_URL,
        timeout: float = settings.PR_CONTEXT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def fetch(self, task_id: int) -> PrContext:
        """Return the PR context of one review task.

        Raises the underlying error unchanged: httpx.HTTPStatusError for a
        non 2xx response, ValueError / ValidationError for a malformed or
        schema violating body. The caller decides how to degrade.
        """
        url = f"{self.base_url}/api/tasks/{task_id}/pr-context"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                context = PrContext.model_validate(resp.json())
        except httpx.HTTPStatusError as error:
            logger.error(
                "Failed to fetch PR context for task %d from Java service: "
                "http_status=%s",
                task_id,
                error.response.status_code,
            )
            raise
        except ValidationError as error:
            logger.error(
                "Failed to fetch PR context for task %d from Java service: "
                "invalid response schema (%s)",
                task_id,
                validation_error_summary(error),
            )
            raise
        except Exception as error:
            logger.error(
                "Failed to fetch PR context for task %d from Java service: %s",
                task_id,
                type(error).__name__,
            )
            raise

        logger.info(
            "Fetched PR context for task %d: files=%d",
            task_id,
            len(context.files),
        )
        return context