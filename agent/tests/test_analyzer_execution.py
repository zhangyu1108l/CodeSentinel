"""Tests for the Phase 7.2 command execution layer.

Model tests are pure. Executor tests start only the trusted Python
interpreter (sys.executable): no external analyzer, no network, no
untrusted code.
"""

import os
import sys
import tempfile

import pytest
from pydantic import ValidationError

from app.analyzers import execution
from app.analyzers.execution import (
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    CommandExecutionRequest,
    CommandExecutionResult,
    ExecutionStatus,
    SubprocessExecutor,
)
from app.schemas.static_analysis import StaticAnalysisErrorCode


def python_command(source: str) -> list[str]:
    return [sys.executable, "-c", source]


def request_data(**overrides):
    data = {
        "command": ["ruff", "check", "agent/app/main.py"],
        "cwd": None,
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "max_output_bytes": DEFAULT_MAX_OUTPUT_BYTES,
    }
    data.update(overrides)
    return data


def result_data(**overrides):
    data = {"status": ExecutionStatus.COMPLETED, "exit_code": 0}
    data.update(overrides)
    return data


class TestExecutionStatus:
    def test_exact_status_values(self):
        assert {status.value for status in ExecutionStatus} == {
            "COMPLETED",
            "UNAVAILABLE",
            "TIMEOUT",
            "ERROR",
        }

    def test_unknown_status_rejected(self):
        with pytest.raises(ValidationError):
            CommandExecutionResult(**result_data(status="RUNNING"))


class TestCommandExecutionRequest:
    def test_defaults_applied(self):
        request = CommandExecutionRequest(command=["ruff", "check"])
        assert request.cwd is None
        assert request.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
        assert request.max_output_bytes == DEFAULT_MAX_OUTPUT_BYTES

    def test_valid_command_kept_as_argument_list(self):
        request = CommandExecutionRequest(
            command=["ruff", "check", "a b.py"]
        )
        assert request.command == ["ruff", "check", "a b.py"]

    def test_missing_command_rejected(self):
        data = request_data()
        del data["command"]
        with pytest.raises(ValidationError):
            CommandExecutionRequest(**data)

    def test_empty_command_rejected(self):
        with pytest.raises(ValidationError):
            CommandExecutionRequest(command=[])

    @pytest.mark.parametrize("executable", ["", " ", "  "])
    def test_blank_executable_rejected(self, executable):
        with pytest.raises(ValidationError):
            CommandExecutionRequest(command=[executable, "check"])

    def test_string_command_rejected(self):
        with pytest.raises(ValidationError):
            CommandExecutionRequest(command="ruff check")

    def test_nul_in_argument_rejected(self):
        with pytest.raises(ValidationError):
            CommandExecutionRequest(command=["ruff", "a\x00b"])

    def test_cwd_accepted(self):
        request = CommandExecutionRequest(
            command=["ruff"], cwd="/tmp/work"
        )
        assert request.cwd == "/tmp/work"

    @pytest.mark.parametrize("cwd", ["", " ", " \t "])
    def test_blank_cwd_rejected(self, cwd):
        with pytest.raises(ValidationError):
            CommandExecutionRequest(command=["ruff"], cwd=cwd)

    def test_nul_cwd_rejected(self):
        with pytest.raises(ValidationError):
            CommandExecutionRequest(command=["ruff"], cwd="a\x00b")

    @pytest.mark.parametrize("timeout", [0, -1, -0.5])
    def test_timeout_not_positive_rejected(self, timeout):
        with pytest.raises(ValidationError):
            CommandExecutionRequest(
                command=["ruff"], timeout_seconds=timeout
            )

    def test_timeout_above_max_rejected(self):
        with pytest.raises(ValidationError):
            CommandExecutionRequest(
                command=["ruff"],
                timeout_seconds=MAX_TIMEOUT_SECONDS + 0.1,
            )

    def test_timeout_at_max_accepted(self):
        request = CommandExecutionRequest(
            command=["ruff"], timeout_seconds=MAX_TIMEOUT_SECONDS
        )
        assert request.timeout_seconds == MAX_TIMEOUT_SECONDS

    @pytest.mark.parametrize("limit", [0, -1])
    def test_output_limit_not_positive_rejected(self, limit):
        with pytest.raises(ValidationError):
            CommandExecutionRequest(
                command=["ruff"], max_output_bytes=limit
            )

    def test_output_limit_above_max_rejected(self):
        with pytest.raises(ValidationError):
            CommandExecutionRequest(
                command=["ruff"],
                max_output_bytes=MAX_OUTPUT_BYTES + 1,
            )

    def test_output_limit_at_max_accepted(self):
        request = CommandExecutionRequest(
            command=["ruff"], max_output_bytes=MAX_OUTPUT_BYTES
        )
        assert request.max_output_bytes == MAX_OUTPUT_BYTES

    def test_serialization_round_trip(self):
        request = CommandExecutionRequest(**request_data())
        recreated = CommandExecutionRequest.model_validate(
            request.model_dump()
        )
        assert recreated == request


class TestCommandExecutionResult:
    def test_completed_with_zero_exit_code(self):
        result = CommandExecutionResult(**result_data())
        assert result.status is ExecutionStatus.COMPLETED
        assert result.error_code is None

    def test_completed_with_nonzero_exit_code_allowed(self):
        result = CommandExecutionResult(**result_data(exit_code=1))
        assert result.exit_code == 1
        assert result.error_code is None

    def test_completed_without_exit_code_rejected(self):
        with pytest.raises(ValidationError):
            CommandExecutionResult(**result_data(exit_code=None))

    def test_completed_with_error_code_rejected(self):
        with pytest.raises(ValidationError):
            CommandExecutionResult(
                **result_data(
                    error_code=StaticAnalysisErrorCode.UNKNOWN
                )
            )

    @pytest.mark.parametrize(
        "status",
        [
            ExecutionStatus.UNAVAILABLE,
            ExecutionStatus.TIMEOUT,
            ExecutionStatus.ERROR,
        ],
    )
    def test_failed_status_requires_error_code(self, status):
        with pytest.raises(ValidationError):
            CommandExecutionResult(**result_data(status=status))

    def test_unavailable_with_exit_code_rejected(self):
        with pytest.raises(ValidationError):
            CommandExecutionResult(
                **result_data(
                    status=ExecutionStatus.UNAVAILABLE,
                    exit_code=3,
                    error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
                )
            )

    def test_unavailable_without_exit_code_valid(self):
        result = CommandExecutionResult(
            status=ExecutionStatus.UNAVAILABLE,
            error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
        )
        assert result.exit_code is None

    def test_timeout_may_carry_exit_code(self):
        result = CommandExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            exit_code=-9,
            error_code=StaticAnalysisErrorCode.TIMEOUT,
        )
        assert result.exit_code == -9

    def test_truncated_false_by_default(self):
        assert CommandExecutionResult(**result_data()).truncated is False

    def test_truncated_from_stdout(self):
        result = CommandExecutionResult(
            **result_data(stdout_truncated=True)
        )
        assert result.truncated is True

    def test_truncated_from_stderr(self):
        result = CommandExecutionResult(
            **result_data(stderr_truncated=True)
        )
        assert result.truncated is True

    def test_negative_duration_rejected(self):
        with pytest.raises(ValidationError):
            CommandExecutionResult(**result_data(duration_ms=-1))

    def test_serialization_round_trip(self):
        result = CommandExecutionResult(
            status=ExecutionStatus.TIMEOUT,
            error_code=StaticAnalysisErrorCode.TIMEOUT,
            stdout="partial",
            duration_ms=120,
        )
        recreated = CommandExecutionResult.model_validate_json(
            result.model_dump_json()
        )
        assert recreated == result


class TestSubprocessExecutor:
    def test_returns_execution_result(self):
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(command=python_command("print(1)"))
        )
        assert isinstance(result, CommandExecutionResult)

    def test_completed_command_returns_stdout(self):
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(
                command=python_command("print('hello')")
            )
        )
        assert result.status is ExecutionStatus.COMPLETED
        assert result.exit_code == 0
        assert result.stdout.strip() == "hello"
        assert result.error_code is None
        assert result.truncated is False
        assert result.duration_ms >= 0

    def test_nonzero_exit_code_stays_completed(self):
        executor = SubprocessExecutor()
        result = executor.execute(
            CommandExecutionRequest(
                command=python_command("import sys; sys.exit(3)")
            )
        )
        assert result.status is ExecutionStatus.COMPLETED
        assert result.exit_code == 3
        assert result.error_code is None

    def test_stderr_captured_separately(self):
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(
                command=python_command(
                    "import sys; sys.stderr.write('boom')"
                )
            )
        )
        assert result.status is ExecutionStatus.COMPLETED
        assert result.stderr.strip() == "boom"
        assert result.stdout == ""

    def test_missing_executable_returns_unavailable(self):
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(
                command=["codesentinel-no-such-tool-9f31", "--json"]
            )
        )
        assert result.status is ExecutionStatus.UNAVAILABLE
        assert result.error_code is StaticAnalysisErrorCode.TOOL_NOT_FOUND
        assert result.exit_code is None
        assert result.stdout == ""
        assert result.stderr == ""

    def test_missing_executable_does_not_spawn(
        self, monkeypatch
    ):
        spawned = []

        def fake_popen(*args, **kwargs):
            spawned.append(args)
            raise RuntimeError("must not be called")

        monkeypatch.setattr(execution.subprocess, "Popen", fake_popen)
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(
                command=["codesentinel-no-such-tool-9f31"]
            )
        )
        assert result.status is ExecutionStatus.UNAVAILABLE
        assert spawned == []

    def test_missing_cwd_returns_spawn_failed(self):
        missing = os.path.join(
            tempfile.gettempdir(), "codesentinel-no-such-dir-9f31"
        )
        assert not os.path.exists(missing)
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(
                command=python_command("print(1)"), cwd=missing
            )
        )
        assert result.status is ExecutionStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.SPAWN_FAILED
        assert result.exit_code is None

    def test_spawn_oserror_returns_spawn_failed(self, monkeypatch):
        def fake_popen(*args, **kwargs):
            raise OSError("spawn refused")

        monkeypatch.setattr(execution.subprocess, "Popen", fake_popen)
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(command=python_command("print(1)"))
        )
        assert result.status is ExecutionStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.SPAWN_FAILED

    def test_unexpected_exception_returns_unknown(self, monkeypatch):
        def fake_popen(*args, **kwargs):
            raise RuntimeError("unexpected")

        monkeypatch.setattr(execution.subprocess, "Popen", fake_popen)
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(command=python_command("print(1)"))
        )
        assert result.status is ExecutionStatus.ERROR
        assert result.error_code is StaticAnalysisErrorCode.UNKNOWN

    def test_timeout_kills_process_and_reports_timeout(self):
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(
                command=python_command("import time; time.sleep(30)"),
                timeout_seconds=0.3,
            )
        )
        assert result.status is ExecutionStatus.TIMEOUT
        assert result.error_code is StaticAnalysisErrorCode.TIMEOUT
        assert result.duration_ms < 5000

    def test_stdout_truncation_flags_and_keeps_prefix(self):
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(
                command=python_command(
                    "import sys; sys.stdout.write('x' * 1000)"
                ),
                max_output_bytes=100,
            )
        )
        assert result.status is ExecutionStatus.COMPLETED
        assert result.stdout_truncated is True
        assert result.stderr_truncated is False
        assert result.stdout == "x" * 100

    def test_stdout_exactly_at_limit_not_truncated(self):
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(
                command=python_command(
                    "import sys; sys.stdout.write('x' * 100)"
                ),
                max_output_bytes=100,
            )
        )
        assert result.stdout_truncated is False
        assert result.stdout == "x" * 100

    def test_stdout_one_byte_over_limit_truncated(self):
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(
                command=python_command(
                    "import sys; sys.stdout.write('x' * 101)"
                ),
                max_output_bytes=100,
            )
        )
        assert result.stdout_truncated is True
        assert result.stdout == "x" * 100

    def test_stderr_truncation_flags(self):
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(
                command=python_command(
                    "import sys; sys.stderr.write('y' * 500)"
                ),
                max_output_bytes=100,
            )
        )
        assert result.stderr_truncated is True
        assert result.stdout_truncated is False
        assert result.stderr == "y" * 100

    def test_small_output_not_truncated(self):
        result = SubprocessExecutor().execute(
            CommandExecutionRequest(
                command=python_command("print('small')")
            )
        )
        assert result.truncated is False

    def test_cwd_is_honored(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = SubprocessExecutor().execute(
                CommandExecutionRequest(
                    command=python_command(
                        "import os; print(os.getcwd())"
                    ),
                    cwd=tmp,
                )
            )
            assert result.status is ExecutionStatus.COMPLETED
            printed = result.stdout.strip()
            assert printed
            assert os.path.samefile(printed, tmp)

    def test_executor_is_reusable(self):
        executor = SubprocessExecutor()
        first = executor.execute(
            CommandExecutionRequest(command=python_command("print(1)"))
        )
        second = executor.execute(
            CommandExecutionRequest(command=python_command("print(2)"))
        )
        assert first.exit_code == 0
        assert second.exit_code == 0
        assert first.stdout.strip() == "1"
        assert second.stdout.strip() == "2"