import logging

from app.worker.java_client import JavaServiceClient
from app.worker.models import TaskMessage

logger = logging.getLogger("codesentinel-ai.handler")


class TaskHandler:
    def __init__(self, java_client: JavaServiceClient = None):
        self.java_client = java_client or JavaServiceClient()

    def handle(self, message: TaskMessage) -> None:
        logger.info(
            "Processing task: taskId=%d, owner=%s, repo=%s, pr=%d, sha=%s",
            message.taskId,
            message.owner,
            message.repo,
            message.prNumber,
            message.commitSha,
        )

        try:
            self.java_client.mark_running(message.taskId)
        except Exception:
            logger.error("Failed to mark task %d as RUNNING, skipping", message.taskId)
            return

        try:
            self._process(message)
        except Exception:
            raise

        try:
            self.java_client.mark_completed(message.taskId)
        except Exception:
            logger.error("Failed to mark task %d as COMPLETED", message.taskId)

    def _process(self, message: TaskMessage) -> None:
        pass