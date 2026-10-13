import logging
from typing import Optional

import httpx

from app.config.settings import settings
from app.schemas.review import ReviewTaskResult

logger = logging.getLogger("codesentinel-ai.java_client")

INTERNAL_TOKEN_HEADER = "X-Internal-Token"


class ResultSubmitConfigurationError(Exception):
    """The result submission is missing its required internal token.

    Raised before any request is sent: a worker without the token must
    fail safely instead of delivering an unauthenticated result, and the
    caller's existing failure path treats it like any other submission
    failure.
    """


class JavaServiceClient:
    def __init__(
        self,
        base_url: str = settings.JAVA_SERVICE_URL,
        internal_token: str = settings.REVIEW_RESULT_INTERNAL_TOKEN,
        submit_timeout: float = settings.RESULT_SUBMIT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.internal_token = internal_token
        self.submit_timeout = submit_timeout

    def mark_running(self, task_id: int) -> None:
        url = f"{self.base_url}/api/tasks/{task_id}/running"
        try:
            resp = httpx.post(url, timeout=10)
            resp.raise_for_status()
            logger.info("Marked task %d as RUNNING", task_id)
        except Exception as e:
            logger.error("Failed to mark task %d as RUNNING: %s", task_id, e)
            raise

    def mark_completed(self, task_id: int) -> None:
        url = f"{self.base_url}/api/tasks/{task_id}/complete"
        try:
            resp = httpx.post(url, timeout=10)
            resp.raise_for_status()
            logger.info("Marked task %d as COMPLETED", task_id)
        except Exception as e:
            logger.error("Failed to mark task %d as COMPLETED: %s", task_id, e)
            raise

    def submit_result(
        self, task_id: int, commit_sha: str, result: ReviewTaskResult
    ) -> dict:
        """Deliver one review result to the durable reception endpoint.

        Returns the parsed reception response for 200/202 (its
        ``duplicate`` and ``publish_status`` describe what the Java side
        stored) or a ``{"status_code": 409, "conflict": True}`` marker
        when an existing, different result is kept. Every other outcome
        raises so the caller's bounded retry chain decides the next
        step. The result's ``report`` field is deliberately not sent.
        """
        token = self._require_internal_token(task_id)
        url = f"{self.base_url}/api/tasks/{task_id}/result"
        payload = {
            "commit_sha": commit_sha,
            "status": result.status,
            "findings": [
                finding.model_dump(mode="json")
                for finding in result.findings
            ],
        }
        try:
            resp = httpx.post(
                url,
                json=payload,
                headers={INTERNAL_TOKEN_HEADER: token},
                timeout=self.submit_timeout,
            )
        except Exception as error:
            logger.error(
                "Failed to submit review result for task %d: %s",
                task_id,
                type(error).__name__,
            )
            raise

        if resp.status_code in (200, 202):
            body = resp.json()
            logger.info(
                "Submitted review result for task %d: http_status=%d, "
                "duplicate=%s, publish_status=%s",
                task_id,
                resp.status_code,
                body.get("duplicate"),
                body.get("publish_status"),
            )
            return {"status_code": resp.status_code, **body}
        if resp.status_code == 409:
            logger.warning(
                "Review result for task %d was not stored (409): an "
                "existing result is kept",
                task_id,
            )
            return {"status_code": 409, "conflict": True}

        logger.error(
            "Failed to submit review result for task %d: http_status=%s",
            task_id,
            resp.status_code,
        )
        resp.raise_for_status()
        # raise_for_status() covers 4xx/5xx; the explicit raise keeps
        # unexpected 2xx/3xx statuses from being treated as success.
        raise RuntimeError(
            f"Unexpected result submission status {resp.status_code}"
        )

    def _require_internal_token(self, task_id: int) -> str:
        token = self.internal_token or ""
        if not token.strip():
            logger.error(
                "Refusing to submit review result for task %d: internal "
                "token is not configured",
                task_id,
            )
            raise ResultSubmitConfigurationError(
                "REVIEW_RESULT_INTERNAL_TOKEN is not configured"
            )
        return token

    def report_failure(self, task_id: int, error_message: str) -> dict:
        url = f"{self.base_url}/api/tasks/{task_id}/failure"
        try:
            resp = httpx.post(
                url,
                json={"errorMessage": error_message},
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(
                "Task %d failure reported: retry=%s, retryCount=%d, status=%s",
                task_id,
                result.get("retry"),
                result.get("retryCount", 0),
                result.get("status"),
            )
            return result
        except Exception as e:
            logger.error("Failed to report task %d failure: %s", task_id, e)
            raise