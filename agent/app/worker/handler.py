import logging

from app.schemas.review import ReviewTaskRequest, ReviewTaskResult
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

        result = self._process(message)

        # The result must be durable on the Java side before the task is
        # marked COMPLETED; a submission failure propagates so the
        # consumer's bounded retry path (report_failure) takes over. A
        # 409 conflict returns normally (an existing result is kept).
        self.java_client.submit_result(
            message.taskId, message.commitSha, result
        )

        try:
            self.java_client.mark_completed(message.taskId)
        except Exception:
            logger.error("Failed to mark task %d as COMPLETED", message.taskId)

    def _process(self, message: TaskMessage) -> ReviewTaskResult:
        request = ReviewTaskRequest(
            task_id=message.taskId,
            repository=f"{message.owner}/{message.repo}",
            pr_number=message.prNumber,
            commit_sha=message.commitSha,
            files=[],
        )
        return self.ai_client.review(request)