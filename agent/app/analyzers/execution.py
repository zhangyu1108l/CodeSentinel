"""Command execution layer for static analysis tools (Phase 7.2).

Runs a trusted analyzer command as an argument list, without a shell, and
returns a structured, testable result. This module never builds commands
from repository or pull request content: the caller supplies a fixed
command, and the framework only executes it and bounds the run.

Design notes:

- shell=False always: commands are argument lists, so untrusted text can
  never turn into shell syntax. A command given as a plain string is
  rejected, never parsed.
- No findings interpretation happens here. A finished process is
  COMPLETED regardless of its exit code, because several analyzers exit
  non zero as soon as they report findings. Mapping output to findings is
  the adapter's concern; parsing JSON is the helper's concern.
- The executable and cwd are checked before spawn, so a missing tool
  becomes an explicit UNAVAILABLE / TOOL_NOT_FOUND result instead of an
  exception.
- stdout and stderr are drained concurrently by daemon threads, each
  capped at max_output_bytes. Bytes beyond the cap are read and discarded
  so the child never blocks on a full pipe, while memory stays bounded by
  the cap. Truncated or incomplete captures are always flagged.
- On timeout the process is killed and reaped; on POSIX the whole process
  group is killed. No raw output, exception text or source code ever
  reaches error_code or the default logs.
"""

import logging
import os
import shutil
import signal
import subprocess
import threading
import time
from enum import Enum
from typing import IO, Protocol

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.static_analysis import StaticAnalysisErrorCode

logger = logging.getLogger("codesentinel-ai.analyzer_execution")

DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_TIMEOUT_SECONDS = 600.0
DEFAULT_MAX_OUTPUT_BYTES = 1_000_000
MAX_OUTPUT_BYTES = 16_000_000

_READ_CHUNK_BYTES = 65536
_TERMINATE_GRACE_SECONDS = 1.0
_READER_JOIN_TIMEOUT_SECONDS = 5.0


class ExecutionStatus(str, Enum):
    """How one process ended, independently of analysis findings.

    COMPLETED means the process started and ended; any exit code is
    possible and none of them means failure here. UNAVAILABLE means the
    executable was not found, so nothing was started. TIMEOUT means the
    deadline passed and the process was killed. ERROR means the process
    could not be started or the run failed unexpectedly.
    """

    COMPLETED = "COMPLETED"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class CommandExecutionRequest(BaseModel):
    """One bounded command execution.

    command is the full argument list with the executable first; it is
    handed to the operating system without any shell. cwd must be supplied
    explicitly by the caller when needed and must point to an existing
    directory. timeout_seconds and max_output_bytes (per stream) are
    capped so a single run can neither hang nor buffer without bound.
    """

    command: list[str]
    cwd: str | None = None
    timeout_seconds: float = Field(
        default=DEFAULT_TIMEOUT_SECONDS, gt=0, le=MAX_TIMEOUT_SECONDS
    )
    max_output_bytes: int = Field(
        default=DEFAULT_MAX_OUTPUT_BYTES, ge=1, le=MAX_OUTPUT_BYTES
    )

    @field_validator("command")
    @classmethod
    def _validate_command(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("command must not be empty")
        if not value[0].strip():
            raise ValueError("command executable must not be blank")
        for argument in value:
            if "\x00" in argument:
                raise ValueError(
                    "command arguments must not contain NUL"
                )
        return value

    @field_validator("cwd")
    @classmethod
    def _validate_cwd(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("cwd must not be blank when provided")
        if "\x00" in value:
            raise ValueError("cwd must not contain NUL")
        return value


class CommandExecutionResult(BaseModel):
    """Structured outcome of one command execution.

    stdout and stderr are decoded with replacement and never raise. Either
    truncated flag means bytes were dropped or could not be fully drained,
    so that stream is incomplete. status COMPLETED means the process
    ended, not that an analysis succeeded or produced findings; non zero
    exit codes stay COMPLETED. error_code is set only for failed runs and
    only carries a finite StaticAnalysisErrorCode, never raw output or
    exception text.
    """

    status: ExecutionStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = Field(default=0, ge=0)
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    error_code: StaticAnalysisErrorCode | None = None

    @model_validator(mode="after")
    def _enforce_status_contract(self) -> "CommandExecutionResult":
        if self.status == ExecutionStatus.COMPLETED:
            if self.exit_code is None:
                raise ValueError(
                    "completed execution must carry an exit code"
                )
            if self.error_code is not None:
                raise ValueError(
                    "completed execution must not carry an error_code"
                )
        else:
            if self.error_code is None:
                raise ValueError(
                    "failed execution must carry an error_code"
                )
            if (
                self.status == ExecutionStatus.UNAVAILABLE
                and self.exit_code is not None
            ):
                raise ValueError(
                    "unavailable executable never produced an exit code"
                )
        return self

    @property
    def truncated(self) -> bool:
        """Whether any captured stream is incomplete."""
        return self.stdout_truncated or self.stderr_truncated


class Executor(Protocol):
    """Runs one command request and returns its raw outcome."""

    def execute(
        self, request: CommandExecutionRequest
    ) -> CommandExecutionResult:
        """Execute request and never raise for tool level failures."""
        ...


class SubprocessExecutor:
    """Default executor: subprocess without a shell, bounded output.

    Stateless and reusable; every call is independent. Injected into
    ToolRunner and into adapter tests as the Executor implementation.
    """

    def execute(
        self, request: CommandExecutionRequest
    ) -> CommandExecutionResult:
        executable = request.command[0]
        if not _executable_available(executable):
            logger.warning(
                "Analyzer executable not found: %s", executable
            )
            return CommandExecutionResult(
                status=ExecutionStatus.UNAVAILABLE,
                error_code=StaticAnalysisErrorCode.TOOL_NOT_FOUND,
            )
        if request.cwd is not None and not os.path.isdir(request.cwd):
            logger.warning(
                "Analyzer cwd is not an existing directory: %s",
                request.cwd,
            )
            return CommandExecutionResult(
                status=ExecutionStatus.ERROR,
                error_code=StaticAnalysisErrorCode.SPAWN_FAILED,
            )

        started = time.monotonic()
        try:
            process = subprocess.Popen(
                request.command,
                cwd=request.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                **_platform_popen_options(),
            )
        except OSError as error:
            logger.warning(
                "Analyzer process failed to start: %s (%s)",
                executable,
                type(error).__name__,
            )
            return CommandExecutionResult(
                status=ExecutionStatus.ERROR,
                error_code=StaticAnalysisErrorCode.SPAWN_FAILED,
                duration_ms=_elapsed_ms(started),
            )
        except Exception as error:
            logger.warning(
                "Analyzer process failed to start: %s (%s)",
                executable,
                type(error).__name__,
            )
            return CommandExecutionResult(
                status=ExecutionStatus.ERROR,
                error_code=StaticAnalysisErrorCode.UNKNOWN,
                duration_ms=_elapsed_ms(started),
            )

        try:
            return self._collect(process, request, started)
        except Exception as error:
            _terminate(process)
            logger.warning(
                "Analyzer run failed unexpectedly: %s (%s)",
                executable,
                type(error).__name__,
            )
            logger.debug(
                "Analyzer run failure detail: %s", executable, exc_info=True
            )
            return CommandExecutionResult(
                status=ExecutionStatus.ERROR,
                error_code=StaticAnalysisErrorCode.UNKNOWN,
                exit_code=process.returncode,
                duration_ms=_elapsed_ms(started),
            )

    def _collect(
        self,
        process: subprocess.Popen,
        request: CommandExecutionRequest,
        started: float,
    ) -> CommandExecutionResult:
        stdout_reader = _StreamReader(request.max_output_bytes)
        stderr_reader = _StreamReader(request.max_output_bytes)
        stdout_thread = _start_reader(process.stdout, stdout_reader)
        stderr_thread = _start_reader(process.stderr, stderr_reader)

        try:
            exit_code = process.wait(timeout=request.timeout_seconds)
            status = ExecutionStatus.COMPLETED
        except subprocess.TimeoutExpired:
            _terminate(process)
            exit_code = process.returncode
            status = ExecutionStatus.TIMEOUT

        _join_reader(stdout_thread)
        _join_reader(stderr_thread)

        duration_ms = _elapsed_ms(started)
        if status == ExecutionStatus.COMPLETED:
            logger.debug(
                "Analyzer command completed: exit_code=%s duration_ms=%d",
                exit_code,
                duration_ms,
            )
            return CommandExecutionResult(
                status=status,
                exit_code=exit_code,
                stdout=stdout_reader.text(),
                stderr=stderr_reader.text(),
                duration_ms=duration_ms,
                stdout_truncated=stdout_reader.truncated,
                stderr_truncated=stderr_reader.truncated,
            )

        logger.warning(
            "Analyzer command timed out after %.1fs",
            request.timeout_seconds,
        )
        return CommandExecutionResult(
            status=status,
            exit_code=exit_code,
            stdout=stdout_reader.text(),
            stderr=stderr_reader.text(),
            duration_ms=duration_ms,
            stdout_truncated=stdout_reader.truncated,
            stderr_truncated=stderr_reader.truncated,
            error_code=StaticAnalysisErrorCode.TIMEOUT,
        )


class _StreamReader:
    """Drains one pipe, keeping at most limit bytes in memory.

    truncated is True when bytes beyond the limit were discarded, when the
    stream read failed or when the reader thread did not finish (for
    example a child process still holding the pipe open), so consumers
    never mistake a partial capture for a complete one.
    """

    def __init__(self, limit: int):
        self._limit = limit
        self._chunks: list[bytes] = []
        self._kept = 0
        self._total = 0
        self._finished = False
        self._failed = False

    def consume(self, stream: IO[bytes]) -> None:
        try:
            while True:
                chunk = stream.read(_READ_CHUNK_BYTES)
                if not chunk:
                    break
                self._total += len(chunk)
                if self._kept < self._limit:
                    keep = chunk[: self._limit - self._kept]
                    self._chunks.append(keep)
                    self._kept += len(keep)
        except (OSError, ValueError):
            self._failed = True
            logger.debug("Analyzer stream read failed", exc_info=True)
        finally:
            self._finished = True
            try:
                stream.close()
            except OSError:
                pass

    @property
    def truncated(self) -> bool:
        return self._total > self._limit or self._failed or not self._finished

    def text(self) -> str:
        return b"".join(self._chunks).decode("utf-8", errors="replace")


def _executable_available(executable: str) -> bool:
    """Whether executable resolves to a runnable file.

    Path like arguments are checked as files, bare names are looked up on
    PATH, so a missing tool degrades before any process is spawned.
    """
    if os.path.sep in executable or (
        os.path.altsep is not None and os.path.altsep in executable
    ):
        return os.path.isfile(executable)
    return shutil.which(executable) is not None


def _platform_popen_options() -> dict:
    """Extra Popen options: own session on POSIX for group kill."""
    if os.name == "posix":
        return {"start_new_session": True}
    return {}


def _terminate(process: subprocess.Popen) -> None:
    """Kill a process (and its group on POSIX) and reap it."""
    killed = False
    if os.name == "posix":
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            killed = True
        except OSError:
            killed = False
    if not killed:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=_TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            pass


def _start_reader(
    stream: IO[bytes], reader: _StreamReader
) -> threading.Thread:
    thread = threading.Thread(
        target=reader.consume, args=(stream,), daemon=True
    )
    thread.start()
    return thread


def _join_reader(thread: threading.Thread) -> None:
    thread.join(timeout=_READER_JOIN_TIMEOUT_SECONDS)


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)