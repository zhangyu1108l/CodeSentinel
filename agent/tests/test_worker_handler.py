"""Tests for TaskHandler with Java API and AI Service integration."""

import logging
from unittest.mock import MagicMock

import pytest

from app.schemas.review import ReviewTaskRequest
from app.worker.ai_client import AiServiceClient
from app.worker.handler import TaskHandler
from app.worker.java_client import JavaServiceClient
from app.worker.models import TaskMessage


def make_message():
    return TaskMessage(
        taskId=1,
        owner="zhangyu1108l",
        repo="CodeSentinel",
        prNumber=42,
        commitSha="abc123",
    )


class TestHandler:
    def setup_method(self):
        self.java = MagicMock(spec=JavaServiceClient)
        self.ai = MagicMock(spec=AiServiceClient)
        self.handler = TaskHandler(java_client=self.java, ai_client=self.ai)

    def test_calls_mark_running(self):
        self.handler.handle(make_message())
        self.java.mark_running.assert_called_once_with(1)

    def test_calls_mark_completed_on_success(self):
        self.handler.handle(make_message())
        self.java.mark_completed.assert_called_once_with(1)

    def test_skips_processing_when_mark_running_fails(self):
        self.java.mark_running.side_effect = RuntimeError("API error")

        self.handler.handle(make_message())

        self.java.mark_running.assert_called_once_with(1)
        self.ai.review.assert_not_called()
        self.java.mark_completed.assert_not_called()

    def test_process_converts_message_to_request(self):
        self.handler._process(make_message())

        self.ai.review.assert_called_once()
        request = self.ai.review.call_args[0][0]
        assert isinstance(request, ReviewTaskRequest)
        assert request.task_id == 1
        assert request.repository == "zhangyu1108l/CodeSentinel"
        assert request.pr_number == 42
        assert request.commit_sha == "abc123"
        assert request.files == []

    def test_ai_review_failure_propagates(self):
        self.ai.review.side_effect = RuntimeError("AI service unreachable")

        with pytest.raises(RuntimeError):
            self.handler.handle(make_message())

        self.java.mark_completed.assert_not_called()


def test_handler_logs_task_info(caplog):
    caplog.set_level(logging.INFO)
    java = MagicMock(spec=JavaServiceClient)
    ai = MagicMock(spec=AiServiceClient)
    handler = TaskHandler(java_client=java, ai_client=ai)
    msg = TaskMessage(
        taskId=5,
        owner="zhangyu1108l",
        repo="CS",
        prNumber=10,
        commitSha="sha123",
    )
    handler.handle(msg)
    assert "taskId=5" in caplog.text
