"""Tests for the Phase 7.2 ToolRunner seam.

A fake executor is injected everywhere: no process is started, no
external tool is required and no network is used.
"""

import pytest
from pydantic import ValidationError

from app.analyzers.execution import (
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    CommandExecutionResult,
    ExecutionStatus,
    SubprocessExecutor,
)
from app.analyzers.tool_runner import ToolRunner
from app.schemas.static_analysis import StaticAnalysisErrorCode


def completed_result(**overrides):
    data = {"status": ExecutionStatus.COMPLETED, "exit_code": 0}
    data.update(overrides)
    return CommandExecutionResult(**data)


class FakeExecutor:
    def __init__(self, result=None):
        self.requests = []
        self.result = result

    def execute(self, request):
        self.requests.append(request)
        if self.result is not None:
            return self.result
        return completed_result()


class TestToolRunnerExecution:
    def test_delegates_to_injected_executor(self):
        executor = FakeExecutor()
        runner = ToolRunner(executor=executor)
        result = runner.run(["ruff", "check", "x.py"])
        assert len(executor.requests) == 1
        assert executor.requests[0].command == ["ruff", "check", "x.py"]
        assert result.status is ExecutionStatus.COMPLETED

    def test_returns_executor_result_unchanged(self):
        expected = completed_result(exit_code=1, stdout="[]")
        executor = FakeExecutor(result=expected)
        runner = ToolRunner(executor=executor)
        assert runner.run(["ruff"]) is expected

    def test_result_is_not_parsed_as_json(self):
        expected = completed_result(stdout="not json at all")
        executor = FakeExecutor(result=expected)
        runner = ToolRunner(executor=executor)
        result = runner.run(["ruff"])
        assert result.stdout == "not json at all"

    def test_failure_result_passes_through(self):
        failure = CommandExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            error_code=StaticAnalysisErrorCode.TIMEOUT,
        )
        executor = FakeExecutor(result=failure)
        runner = ToolRunner(executor=executor)
        result = runner.run(["ruff"])
        assert result.status is ExecutionStatus.TIMEOUT

    def test_default_executor_is_subprocess_executor(self):
        runner = ToolRunner()
        assert isinstance(runner.executor, SubprocessExecutor)

    def test_two_runs_build_two_requests(self):
        executor = FakeExecutor()
        runner = ToolRunner(executor=executor)
        runner.run(["ruff", "a.py"])
        runner.run(["ruff", "b.py"])
        assert len(executor.requests) == 2
        assert executor.requests[0].command == ["ruff", "a.py"]
        assert executor.requests[1].command == ["ruff", "b.py"]


class TestToolRunnerDefaults:
    def test_runner_defaults_applied_to_request(self):
        executor = FakeExecutor()
        runner = ToolRunner(executor=executor)
        runner.run(["ruff"])
        request = executor.requests[0]
        assert request.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
        assert request.max_output_bytes == DEFAULT_MAX_OUTPUT_BYTES
        assert request.cwd is None

    def test_custom_runner_defaults_applied(self):
        executor = FakeExecutor()
        runner = ToolRunner(
            executor=executor,
            timeout_seconds=12.5,
            max_output_bytes=2048,
        )
        runner.run(["ruff"])
        request = executor.requests[0]
        assert request.timeout_seconds == 12.5
        assert request.max_output_bytes == 2048

    def test_per_call_overrides_applied(self):
        executor = FakeExecutor()
        runner = ToolRunner(
            executor=executor,
            timeout_seconds=12.5,
            max_output_bytes=2048,
        )
        runner.run(
            ["ruff"], timeout_seconds=3, max_output_bytes=99
        )
        request = executor.requests[0]
        assert request.timeout_seconds == 3
        assert request.max_output_bytes == 99

    def test_cwd_passed_through(self):
        executor = FakeExecutor()
        runner = ToolRunner(executor=executor)
        runner.run(["ruff"], cwd="/tmp/work")
        assert executor.requests[0].cwd == "/tmp/work"

    def test_tuple_command_becomes_argument_list(self):
        executor = FakeExecutor()
        runner = ToolRunner(executor=executor)
        runner.run(("ruff", "check"))
        assert executor.requests[0].command == ["ruff", "check"]


class TestToolRunnerRejectsUnsafeInput:
    def test_string_command_rejected(self):
        runner = ToolRunner(executor=FakeExecutor())
        with pytest.raises(ValueError):
            runner.run("ruff check x.py")

    def test_bytes_command_rejected(self):
        runner = ToolRunner(executor=FakeExecutor())
        with pytest.raises(ValueError):
            runner.run(b"ruff")

    def test_empty_command_rejected(self):
        executor = FakeExecutor()
        runner = ToolRunner(executor=executor)
        with pytest.raises(ValidationError):
            runner.run([])
        assert executor.requests == []

    def test_blank_executable_rejected(self):
        executor = FakeExecutor()
        runner = ToolRunner(executor=executor)
        with pytest.raises(ValidationError):
            runner.run(["   ", "check"])
        assert executor.requests == []

    @pytest.mark.parametrize(
        "timeout", [0, -1, MAX_TIMEOUT_SECONDS + 1]
    )
    def test_invalid_default_timeout_rejected(self, timeout):
        with pytest.raises(ValueError):
            ToolRunner(executor=FakeExecutor(), timeout_seconds=timeout)

    @pytest.mark.parametrize("limit", [0, -1, MAX_OUTPUT_BYTES + 1])
    def test_invalid_default_output_limit_rejected(self, limit):
        with pytest.raises(ValueError):
            ToolRunner(
                executor=FakeExecutor(), max_output_bytes=limit
            )

    @pytest.mark.parametrize(
        "timeout", [0, -1, MAX_TIMEOUT_SECONDS + 1]
    )
    def test_invalid_per_call_timeout_rejected(self, timeout):
        executor = FakeExecutor()
        runner = ToolRunner(executor=executor)
        with pytest.raises(ValidationError):
            runner.run(["ruff"], timeout_seconds=timeout)
        assert executor.requests == []