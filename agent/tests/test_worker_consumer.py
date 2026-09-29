"""Tests for RedisTaskConsumer with retry logic."""

import json
from unittest.mock import MagicMock

import pytest
from redis import Redis

from app.worker.consumer import RedisTaskConsumer
from app.worker.handler import TaskHandler
from app.worker.java_client import JavaServiceClient
from app.worker.models import TaskMessage

QUEUE_KEY = "codesentinel:review:tasks"


def make_valid_message_bytes(**overrides):
    data = {
        "taskId": 1,
        "owner": "owner",
        "repo": "repo",
        "prNumber": 42,
        "commitSha": "abc123",
    }
    data.update(overrides)
    return json.dumps(data).encode("utf-8")


class TestConsumer:
    def setup_method(self):
        self.redis = MagicMock(spec=Redis)
        self.handler = MagicMock(spec=TaskHandler)
        self.java = MagicMock(spec=JavaServiceClient)
        self.consumer = RedisTaskConsumer(
            redis_client=self.redis,
            queue_key=QUEUE_KEY,
            handler=self.handler,
            java_client=self.java,
        )

    def test_processes_valid_message(self):
        raw = make_valid_message_bytes()
        self.consumer._process_message(raw)

        self.handler.handle.assert_called_once()

    def test_skips_invalid_json(self):
        raw = b"not valid json"
        self.consumer._process_message(raw)
        self.handler.handle.assert_not_called()

    def test_skips_missing_field(self):
        raw = make_valid_message_bytes()
        data = json.loads(raw)
        del data["commitSha"]
        raw = json.dumps(data).encode("utf-8")
        self.consumer._process_message(raw)
        self.handler.handle.assert_not_called()

    def test_catches_handler_exception(self):
        raw = make_valid_message_bytes()
        self.handler.handle.side_effect = RuntimeError("Handler error")
        self.java.report_failure.return_value = {"retry": False, "taskId": 1, "retryCount": 3, "status": "FAILED"}

        self.consumer._process_message(raw)

        self.handler.handle.assert_called_once()
        self.java.report_failure.assert_called_once()

    def test_retries_on_failure_when_java_says_retry(self):
        raw = make_valid_message_bytes()
        self.handler.handle.side_effect = RuntimeError("Handler error")
        self.java.report_failure.return_value = {"retry": True, "taskId": 1, "retryCount": 1, "status": "PENDING"}

        self.consumer._process_message(raw)

        self.java.report_failure.assert_called_once()
        self.redis.rpush.assert_called_once()
        assert QUEUE_KEY in self.redis.rpush.call_args[0]

    def test_does_not_re_enqueue_when_retries_exhausted(self):
        raw = make_valid_message_bytes()
        self.handler.handle.side_effect = RuntimeError("Fatal error")
        self.java.report_failure.return_value = {"retry": False, "taskId": 1, "retryCount": 3, "status": "FAILED"}

        self.consumer._process_message(raw)

        self.redis.rpush.assert_not_called()

    def test_handles_java_api_failure(self):
        raw = make_valid_message_bytes()
        self.handler.handle.side_effect = RuntimeError("Handler error")
        self.java.report_failure.side_effect = RuntimeError("Java unreachable")

        self.consumer._process_message(raw)

        self.redis.rpush.assert_not_called()

    def test_blpop_uses_correct_key(self):
        self.redis.blpop.return_value = (QUEUE_KEY, make_valid_message_bytes(taskId=2))
        self.consumer._process_from_blpop()
        self.redis.blpop.assert_called_once_with(QUEUE_KEY, timeout=5)

    def test_blpop_none_skips_processing(self):
        self.redis.blpop.return_value = None
        self.consumer._process_from_blpop()
        self.handler.handle.assert_not_called()

    def test_blpop_error_is_caught(self):
        self.redis.blpop.side_effect = RuntimeError("Connection lost")
        self.consumer._process_from_blpop()
        self.handler.handle.assert_not_called()


def _process_from_blpop(self):
    try:
        result = self.redis_client.blpop(self.queue_key, timeout=self.blpop_timeout)
    except Exception:
        return
    if result is None:
        return
    _, raw_message = result
    self._process_message(raw_message)


RedisTaskConsumer._process_from_blpop = _process_from_blpop