"""Ruff static analysis adapter (Phase 7.3).

Runs Ruff in JSON output mode through the Phase 7.2 ToolRunner and maps
its diagnostics onto the Phase 7.1 contract. Only the caller supplied
repository directory and Python file paths are ever checked: Ruff is
never asked to scan a directory, and no pull request content becomes part
of the command.

Command form:

    ruff check --output-format json --isolated --no-cache <files...>

run with cwd set to the repository directory and relative file arguments.
--isolated stops Ruff from reading configuration files of the reviewed
repository (which could otherwise change tool behaviour); --no-cache
keeps the workspace free of tool side effects. Rule selection stays on
Ruff's defaults until the rule engine phase makes it explicit.

Mapping policy:

- rule_id is the Ruff rule code (for example F401). Category derives from
  the rule code prefix with a small explicit override table, defaulting to
  QUALITY; severity derives from category (SECURITY HIGH, BUG MEDIUM,
  PERFORMANCE LOW, QUALITY INFO). No new enum values are introduced; the
  Validator may adjust severity later.
- Exit codes 0 (clean) and 1 (diagnostics found) are accepted regardless
  of whether findings exist. Any other completed exit code means Ruff
  reported a run level error and becomes ERROR / PROCESS_FAILED.
- A truncated stdout, empty output, invalid JSON or any structurally
  unmappable diagnostic invalidates the whole run: the result is
  PARSE_ERROR and carries no findings, so partial output can never
  masquerade as a complete analysis. A truncated stderr alone does not
  affect the JSON result.
- Diagnostic file paths are normalized to repository relative forward
  slash paths and must resolve inside the repository directory and belong
  to the requested target set.

Logs never contain stdout, stderr, diagnostic messages or source code;
failures are reported only through finite StaticAnalysisErrorCode values.
"""

import logging
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.analyzers.execution import ExecutionStatus
from app.analyzers.json_output import JsonStatus, parse_json_output
from app.analyzers.path_guard import (
    map_output_path,
    validate_repo_dir,
    validate_targets,
)
from app.analyzers.tool_runner import ToolRunner
from app.schemas.review import Category, Severity
from app.schemas.static_analysis import (
    StaticAnalysisErrorCode,
    StaticAnalysisFinding,
    StaticAnalysisResult,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)

logger = logging.getLogger("codesentinel-ai.ruff_adapter")

RUFF_EXECUTABLE = "ruff"

_TOOL = StaticAnalysisTool.RUFF
_ALLOWED_SUFFIXES = (".py", ".pyi")
_ACCEPTED_EXIT_CODES = frozenset({0, 1})

_EXECUTION_STATUS_MAP = {
    ExecutionStatus.UNAVAILABLE: StaticAnalysisStatus.UNAVAILABLE,
    ExecutionStatus.TIMEOUT: StaticAnalysisStatus.TIMEOUT,
    ExecutionStatus.ERROR: StaticAnalysisStatus.ERROR,
}

_CATEGORY_BY_PREFIX = {
    "S": Category.SECURITY,
    "B": Category.BUG,
    "TRY": Category.BUG,
    "BLE": Category.BUG,
    "PERF": Category.PERFORMANCE,
}

_CATEGORY_BY_CODE = {
    "F811": Category.BUG,
    "F821": Category.BUG,
    "F822": Category.BUG,
    "F823": Category.BUG,
}

_SEVERITY_BY_CATEGORY = {
    Category.SECURITY: Severity.HIGH,
    Category.BUG: Severity.MEDIUM,
    Category.PERFORMANCE: Severity.LOW,
    Category.QUALITY: Severity.INFO,
}


class _RuffPosition(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    row: int = Field(ge=1)


class _RuffDiagnostic(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    code: str
    message: str
    filename: str
    location: _RuffPosition
    end_location: _RuffPosition


class _OutputError(Exception):
    """Unmappable tool output; carries only a safe error code."""

    def __init__(self, error_code: StaticAnalysisErrorCode):
        super().__init__(error_code.value)
        self.error_code = error_code


class RuffAdapter:
    """Maps one bounded Ruff run onto the static analysis contract."""

    def __init__(
        self, runner: ToolRunner, executable: str = RUFF_EXECUTABLE
    ):
        if (
            not isinstance(executable, str)
            or not executable
            or not executable.strip()
        ):
            raise ValueError("executable must not be blank")
        self.runner = runner
        self.executable = executable

    def analyze(
        self, repo_dir: str, file_paths: Sequence[str]
    ) -> StaticAnalysisResult:
        """Check the given repository relative Python files.

        repo_dir must be an existing directory; every target must be a
        repository relative .py / .pyi file that exists inside repo_dir.
        Invalid input raises ValueError (a caller defect), while every
        tool level failure degrades into a StaticAnalysisResult instead.
        """
        root = validate_repo_dir(repo_dir)
        targets = validate_targets(
            root, file_paths, suffixes=_ALLOWED_SUFFIXES
        )

        command = [
            self.executable,
            "check",
            "--output-format",
            "json",
            "--isolated",
            "--no-cache",
            *targets,
        ]
        logger.debug(
            "Running Ruff on %d target file(s)", len(targets)
        )
        execution = self.runner.run(command, cwd=root)
        return self._to_result(execution, root, targets)

    def _to_result(
        self,
        execution,
        repo_dir: str,
        targets: list[str],
    ) -> StaticAnalysisResult:
        if execution.status != ExecutionStatus.COMPLETED:
            status = _EXECUTION_STATUS_MAP[execution.status]
            return _failure(
                execution,
                status,
                execution.error_code or StaticAnalysisErrorCode.UNKNOWN,
            )

        if execution.exit_code not in _ACCEPTED_EXIT_CODES:
            logger.warning(
                "Ruff run failed: exit_code=%s", execution.exit_code
            )
            return _failure(
                execution,
                StaticAnalysisStatus.ERROR,
                StaticAnalysisErrorCode.PROCESS_FAILED,
            )

        if execution.stdout_truncated:
            logger.warning(
                "Ruff stdout was truncated; result rejected"
            )
            return _failure(
                execution,
                StaticAnalysisStatus.PARSE_ERROR,
                StaticAnalysisErrorCode.INVALID_OUTPUT,
            )

        parsed = parse_json_output(execution.stdout)
        if parsed.status != JsonStatus.VALID:
            logger.warning(
                "Ruff output is not valid JSON: json_status=%s",
                parsed.status.value,
            )
            return _failure(
                execution,
                StaticAnalysisStatus.PARSE_ERROR,
                StaticAnalysisErrorCode.INVALID_OUTPUT,
            )

        try:
            findings = _map_payload(parsed.data, repo_dir, targets)
        except _OutputError as error:
            logger.warning(
                "Ruff output rejected: error_code=%s",
                error.error_code.value,
            )
            return _failure(
                execution, StaticAnalysisStatus.PARSE_ERROR, error.error_code
            )

        logger.debug(
            "Ruff analysis finished: findings=%d exit_code=%s "
            "duration_ms=%d",
            len(findings),
            execution.exit_code,
            execution.duration_ms,
        )
        return StaticAnalysisResult(
            tool=_TOOL,
            status=StaticAnalysisStatus.OK,
            findings=findings,
            exit_code=execution.exit_code,
            duration_ms=execution.duration_ms,
        )


def _failure(
    execution, status: StaticAnalysisStatus, error_code
) -> StaticAnalysisResult:
    return StaticAnalysisResult(
        tool=_TOOL,
        status=status,
        exit_code=execution.exit_code,
        duration_ms=execution.duration_ms,
        error_code=error_code,
    )


def _map_payload(
    payload, repo_dir: str, targets: list[str]
) -> list[StaticAnalysisFinding]:
    if not isinstance(payload, list):
        raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)

    allowed = set(targets)
    findings: list[StaticAnalysisFinding] = []
    for entry in payload:
        try:
            diagnostic = _RuffDiagnostic.model_validate(entry)
        except ValidationError:
            raise _OutputError(
                StaticAnalysisErrorCode.SCHEMA_MISMATCH
            ) from None

        if not diagnostic.code.strip() or not diagnostic.message.strip():
            raise _OutputError(
                StaticAnalysisErrorCode.SCHEMA_MISMATCH
            )

        file_path = map_output_path(
            diagnostic.filename, repo_dir, allowed
        )
        if file_path is None:
            raise _OutputError(
                StaticAnalysisErrorCode.SCHEMA_MISMATCH
            )

        try:
            finding = StaticAnalysisFinding(
                tool=_TOOL,
                rule_id=diagnostic.code,
                category=_category_for(diagnostic.code),
                severity=_severity_for(diagnostic.code),
                message=diagnostic.message,
                file_path=file_path,
                start_line=diagnostic.location.row,
                end_line=diagnostic.end_location.row,
            )
        except ValidationError:
            raise _OutputError(
                StaticAnalysisErrorCode.SCHEMA_MISMATCH
            ) from None
        findings.append(finding)

    return findings


def _category_for(rule_id: str) -> Category:
    override = _CATEGORY_BY_CODE.get(rule_id)
    if override is not None:
        return override
    return _CATEGORY_BY_PREFIX.get(_letters_prefix(rule_id), Category.QUALITY)


def _severity_for(rule_id: str) -> Severity:
    return _SEVERITY_BY_CATEGORY[_category_for(rule_id)]


def _letters_prefix(rule_id: str) -> str:
    index = 0
    while index < len(rule_id) and rule_id[index].isalpha():
        index += 1
    return rule_id[:index]