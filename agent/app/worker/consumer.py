import json
import logging

from pydantic import ValidationError
from redis import Redis

from app.worker.handler import TaskHandler
from app.worker.java_client import JavaServiceClient
from app.worker.models import TaskMessage

logger = logging.getLogger("codesentinel-ai.consumer")


class RedisTaskConsumer:
    def __init__(
        self,
        redis_client: Redis,
        queue_key: str,
        handler: TaskHandler,
        java_client: JavaServiceClient = None,
        blpop_timeout: int = 5,
    ):
        self.redis_client = redis_client
        self.queue_key = queue_key
        self.handler = handler
        self.java_client = java_client or JavaServiceClient()
        self.blpop_timeout = blpop_timeout

    def run(self) -> None:
        logger.info("Consumer started, queue=%s", self.queue_key)
        while True:
            try:
                result = self.redis_client.blpop(
                    self.queue_key, timeout=self.blpop_timeout
                )
            except Exception as e:
                logger.error("Redis BLPOP error: %s", e)
                continue

            if result is None:
                continue

            _, raw_message = result
            self._process_message(raw_message)

    def _process_message(self, raw_message: bytes) -> None:
        try:
            json_str = raw_message.decode("utf-8")
        except UnicodeDecodeError as e:
            logger.error("Failed to decode message as UTF-8: %s", e)
            return

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse message JSON: %s", e)
            return

        try:
            message = TaskMessage(**data)
        except ValidationError as e:
            logger.error("Invalid task message: %s, raw=%s", e, json_str)
            return

        try:
            self.handler.handle(message)
        except Exception as e:
            self._handle_task_failure(message, e)

    def _handle_task_failure(self, message: TaskMessage, error: Exception) -> None:
        error_message = f"Handler error: {error}"
        logger.error("Task %d failed: %s", message.taskId, error)

        try:
            result = self.java_client.report_failure(
                message.taskId, error_message
            )
        except Exception as e2:
            logger.error(
                "Failed to report task %d failure to Java: %s",
                message.taskId, e2,
            )
            return

        if result.get("retry"):
            logger.info(
                "Retrying task %d (retryCount=%d)",
                message.taskId, result.get("retryCount", 0),
            )
            self._re_enqueue(message)
        else:
            logger.info(
                "Task %d exhausted retries, status=%s",
                message.taskId, result.get("status"),
            )

    def _re_enqueue(self, message: TaskMessage) -> None:
        json_str = message.model_dump_json()
        try:
            self.redis_client.rpush(self.queue_key, json_str)
            logger.info("Re-enqueued task %d to queue %s", message.taskId, self.queue_key)
        except Exception as e:
            logger.error("Failed to re-enqueue task %d: %s", message.taskId, e)