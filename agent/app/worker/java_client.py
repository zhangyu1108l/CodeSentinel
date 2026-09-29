import logging
from typing import Optional

import httpx

from app.config.settings import settings

logger = logging.getLogger("codesentinel-ai.java_client")


class JavaServiceClient:
    def __init__(self, base_url: str = settings.JAVA_SERVICE_URL):
        self.base_url = base_url.rstrip("/")

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