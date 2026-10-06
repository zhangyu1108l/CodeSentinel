import logging

from app.schemas.review import ReviewTaskRequest
from app.worker.ai_client import AiServiceClient
from app.worker.java_client import JavaServiceClient
from app.worker.models import TaskMessage

logger = logging.getLogger("codesentinel-ai.handler")


class TaskHandler:
    def __init__(
        self,
        java_client: JavaServiceClient = None,
        ai_client: AiServiceClient = None,
    ):
        self.java_client = java_client or JavaServiceClient()
        self.ai_client = ai_client or AiServiceClient()

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
        request = ReviewTaskRequest(
            task_id=message.taskId,
            repository=f"{message.owner}/{message.repo}",
            pr_number=message.prNumber,
            commit_sha=message.commitSha,
            files=[],
        )
        self.ai_client.review(request)