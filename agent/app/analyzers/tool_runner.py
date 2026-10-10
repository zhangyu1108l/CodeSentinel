"""ToolRunner: tool level entry point over an injectable executor.

ToolRunner is the seam adapters use: it applies bounded timeout and output
limit defaults, builds a CommandExecutionRequest and delegates the run to
an injected Executor (SubprocessExecutor by default). It never parses
JSON, interprets exit codes or produces findings, so a failed or empty
run can never be mistaken for a clean analysis.

Commands are always argument lists owned by the application; a plain
string is rejected instead of being parsed, keeping pull request content
out of shell syntax. No adapter, scheduler or aggregation logic lives
here.
"""

from collections.abc import Sequence

from app.analyzers.execution import (
    DEFAULT_MAX_OUTPUT_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_OUTPUT_BYTES,
    MAX_TIMEOUT_SECONDS,
    CommandExecutionRequest,
    CommandExecutionResult,
    Executor,
    SubprocessExecutor,
)


class ToolRunner:
    """Runs bounded analyzer commands through an injectable executor."""

    def __init__(
        self,
        executor: Executor | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ):
        self.executor: Executor = (
            SubprocessExecutor() if executor is None else executor
        )
        if not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ValueError(
                "timeout_seconds must be greater than 0 and at most "
                f"{MAX_TIMEOUT_SECONDS}"
            )
        if not 1 <= max_output_bytes <= MAX_OUTPUT_BYTES:
            raise ValueError(
                "max_output_bytes must be at least 1 and at most "
                f"{MAX_OUTPUT_BYTES}"
            )
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def run(
        self,
        command: Sequence[str],
        cwd: str | None = None,
        timeout_seconds: float | None = None,
        max_output_bytes: int | None = None,
    ) -> CommandExecutionResult:
        """Execute one analyzer command and return its raw outcome.

        command must be an argument list with the executable first; a
        string or bytes value is rejected because this framework never
        interprets shell syntax. timeout_seconds and max_output_bytes
        override the runner defaults for this call only.
        """
        if isinstance(command, (str, bytes)):
            raise ValueError(
                "command must be an argument list, not a string"
            )
        request = CommandExecutionRequest(
            command=list(command),
            cwd=cwd,
            timeout_seconds=(
                self.timeout_seconds
                if timeout_seconds is None
                else timeout_seconds
            ),
            max_output_bytes=(
                self.max_output_bytes
                if max_output_bytes is None
                else max_output_bytes
            ),
        )
        return self.executor.execute(request)