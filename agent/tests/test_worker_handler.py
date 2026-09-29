"""Tests for TaskHandler with Java API integration."""

import logging
from unittest.mock import MagicMock

from app.worker.handler import TaskHandler
from app.worker.java_client import JavaServiceClient
from app.worker.models import TaskMessage


class TestHandler:
    def setup_method(self):
        self.java = MagicMock(spec=JavaServiceClient)
        self.handler = TaskHandler(java_client=self.java)

    def test_calls_mark_running(self):
        msg = TaskMessage(taskId=1, owner="o", repo="r", prNumber=42, commitSha="abc")
        self.handler.handle(msg)
        self.java.mark_running.assert_called_once_with(1)

    def test_calls_mark_completed_on_success(self):
        msg = TaskMessage(taskId=1, owner="o", repo="r", prNumber=42, commitSha="abc")
        self.handler.handle(msg)
        self.java.mark_completed.assert_called_once_with(1)

    def test_skips_processing_when_mark_running_fails(self):
        self.java.mark_running.side_effect = RuntimeError("API error")
        msg = TaskMessage(taskId=1, owner="o", repo="r", prNumber=42, commitSha="abc")

        self.handler.handle(msg)

        self.java.mark_running.assert_called_once_with(1)
        self.java.mark_completed.assert_not_called()


def test_handler_logs_task_info(caplog):
    caplog.set_level(logging.INFO)
    java = MagicMock(spec=JavaServiceClient)
    handler = TaskHandler(java_client=java)
    msg = TaskMessage(taskId=5, owner="zhangyu1108l", repo="CS", prNumber=10, commitSha="sha123")
    handler.handle(msg)
    assert "taskId=5" in caplog.text