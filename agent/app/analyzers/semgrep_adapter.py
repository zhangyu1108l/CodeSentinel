"""Semgrep static analysis adapter (Phase 7.5).

Runs Semgrep in JSON output mode through the Phase 7.2 ToolRunner and maps
its findings onto the Phase 7.1 contract. Semgrep supports many languages,
so unlike the Ruff and Bandit adapters no file suffix restriction is
applied: the caller decides which existing repository files to scan.

Trusted rule configuration:

    semgrep scan --json --metrics=off --disable-version-check
        --no-git-ignore --config=<absolute trusted config> <files...>

run with cwd set to the repository directory and relative file arguments.
The rule config is supplied by the caller and must be an existing file
outside the reviewed repository; a config that resolves inside the
repository is rejected. --config auto, registry names and URLs are never
used, and the config must be a real file, so no rule is ever downloaded or
taken from the untrusted workspace. --metrics=off and
--disable-version-check keep the run free of implicit network traffic, and
--no-git-ignore stops an untrusted .gitignore from hiding explicit
targets. A repository .semgrepignore can still hide targets; that is
detected (see below) instead of trusted.

Mapping policy:

- rule_id is check_id; message is extra.message. extra.severity maps
  explicitly: ERROR -> HIGH, WARNING -> MEDIUM, INFO -> LOW. This is a
  translation of the tool's own severity, not a final risk verdict; the
  Validator may adjust it. Unknown severities invalidate the run.
- Category prefers trusted rule metadata (extra.metadata.category:
  security -> SECURITY, correctness -> BUG, performance -> PERFORMANCE,
  best-practice / maintainability / portability -> QUALITY). When that is
  missing or unrecognized, a well known registry segment of check_id is
  used; the conservative default is QUALITY, so a Semgrep result is never
  assumed to be a security issue without evidence.
- start_line is start.line; end_line is end.line when present, otherwise
  start_line. Missing or contradictory line data invalidates the run
  instead of fabricating a location.
- Exit codes 0 (clean) and 1 (findings reported) are accepted; the JSON
  results decide what was found. Any other completed exit code (2 fatal,
  3 invalid target, 5 unparseable YAML, 7 missing configuration, ...)
  becomes ERROR / PROCESS_FAILED.
- A non empty errors list, or a paths.scanned list that does not cover
  every requested target, means the scan is incomplete: the run becomes
  ERROR / PROCESS_FAILED with no findings, so partial scans never
  masquerade as complete ones.
- A truncated stdout, empty output, invalid JSON or any unmappable result
  invalidates the whole run (PARSE_ERROR, no findings). A truncated stderr
  alone does not affect the JSON result.
- Result paths are normalized to repository relative forward slash paths
  and must belong to the requested target set. The path guard lives here
  and is self contained; it intentionally does not reuse or extend the
  private helpers of the Ruff and Bandit adapters.

Logs never contain stdout, stderr, messages or source code; failures are
reported only through finite StaticAnalysisErrorCode values.
"""

import logging
import os
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.analyzers.execution import ExecutionStatus
from app.analyzers.json_output import JsonStatus, parse_json_output
from app.analyzers.path_guard import (
    is_within,
    map_output_path,
    normalize_output_path,
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

logger = logging.getLogger("codesentinel-ai.semgrep_adapter")

SEMGREP_EXECUTABLE = "semgrep"

_TOOL = StaticAnalysisTool.SEMGREP
_ACCEPTED_EXIT_CODES = frozenset({0, 1})

_SEVERITY_MAP = {
    "ERROR": Severity.HIGH,
    "WARNING": Severity.MEDIUM,
    "INFO": Severity.LOW,
}

_CATEGORY_BY_NAME = {
    "security": Category.SECURITY,
    "correctness": Category.BUG,
    "performance": Category.PERFORMANCE,
    "best-practice": Category.QUALITY,
    "maintainability": Category.QUALITY,
    "portability": Category.QUALITY,
}

_EXECUTION_STATUS_MAP = {
    ExecutionStatus.UNAVAILABLE: StaticAnalysisStatus.UNAVAILABLE,
    ExecutionStatus.TIMEOUT: StaticAnalysisStatus.TIMEOUT,
    ExecutionStatus.ERROR: StaticAnalysisStatus.ERROR,
}


class _SemgrepPosition(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    line: int = Field(ge=1)


class _SemgrepExtra(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    message: str
    severity: str
    metadata: dict | None = None


class _SemgrepResult(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    check_id: str
    path: str
    start: _SemgrepPosition
    end: _SemgrepPosition | None = None
    extra: _SemgrepExtra


class _SemgrepPaths(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    scanned: list[str]


class _SemgrepReport(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    results: list[_SemgrepResult]
    errors: list
    paths: _SemgrepPaths


class _OutputError(Exception):
    """Unmappable tool output; carries only a safe error code."""

    def __init__(self, error_code: StaticAnalysisErrorCode):
        super().__init__(error_code.value)
        self.error_code = error_code


class SemgrepAdapter:
    """Maps one bounded Semgrep run onto the static analysis contract."""

    def __init__(
        self,
        runner: ToolRunner,
        config_path: str,
        executable: str = SEMGREP_EXECUTABLE,
    ):
        if (
            not isinstance(executable, str)
            or not executable
            or not executable.strip()
        ):
            raise ValueError("executable must not be blank")
        self.runner = runner
        self.executable = executable
        self.config_path = _validate_config_path(config_path)

    def analyze(
        self, repo_dir: str, file_paths: Sequence[str]
    ) -> StaticAnalysisResult:
        """Scan the given repository files with the trusted rule config.

        repo_dir must be an existing directory; every target must be an
        existing repository relative file. The rule config must not live
        inside the reviewed repository. Invalid input raises ValueError (a
        caller defect), while every tool level failure degrades into a
        StaticAnalysisResult instead.
        """
        root = validate_repo_dir(repo_dir)
        if is_within(root, self.config_path):
            raise ValueError(
                "semgrep config must not live inside the reviewed "
                "repository"
            )
        targets = validate_targets(root, file_paths)

        command = [
            self.executable,
            "scan",
            "--json",
            "--metrics=off",
            "--disable-version-check",
            "--no-git-ignore",
            f"--config={self.config_path}",
            *targets,
        ]
        logger.debug(
            "Running Semgrep on %d target file(s)", len(targets)
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
                "Semgrep run failed: exit_code=%s", execution.exit_code
            )
            return _failure(
                execution,
                StaticAnalysisStatus.ERROR,
                StaticAnalysisErrorCode.PROCESS_FAILED,
            )

        if execution.stdout_truncated:
            logger.warning(
                "Semgrep stdout was truncated; result rejected"
            )
            return _failure(
                execution,
                StaticAnalysisStatus.PARSE_ERROR,
                StaticAnalysisErrorCode.INVALID_OUTPUT,
            )

        parsed = parse_json_output(execution.stdout)
        if parsed.status != JsonStatus.VALID:
            logger.warning(
                "Semgrep output is not valid JSON: json_status=%s",
                parsed.status.value,
            )
            return _failure(
                execution,
                StaticAnalysisStatus.PARSE_ERROR,
                StaticAnalysisErrorCode.INVALID_OUTPUT,
            )

        try:
            report = _SemgrepReport.model_validate(parsed.data)
        except ValidationError:
            logger.warning("Semgrep output structure rejected")
            return _failure(
                execution,
                StaticAnalysisStatus.PARSE_ERROR,
                StaticAnalysisErrorCode.SCHEMA_MISMATCH,
            )

        if report.errors:
            logger.warning(
                "Semgrep reported scan errors; result rejected"
            )
            return _failure(
                execution,
                StaticAnalysisStatus.ERROR,
                StaticAnalysisErrorCode.PROCESS_FAILED,
            )

        try:
            scanned = _scanned_keys(report, repo_dir)
        except _OutputError as error:
            logger.warning(
                "Semgrep scanned paths rejected: error_code=%s",
                error.error_code.value,
            )
            return _failure(
                execution, StaticAnalysisStatus.PARSE_ERROR, error.error_code
            )

        if not _covers_targets(scanned, targets):
            logger.warning(
                "Semgrep did not scan every requested target; "
                "result rejected"
            )
            return _failure(
                execution,
                StaticAnalysisStatus.ERROR,
                StaticAnalysisErrorCode.PROCESS_FAILED,
            )

        try:
            findings = _map_results(report, repo_dir, targets)
        except _OutputError as error:
            logger.warning(
                "Semgrep output rejected: error_code=%s",
                error.error_code.value,
            )
            return _failure(
                execution, StaticAnalysisStatus.PARSE_ERROR, error.error_code
            )

        logger.debug(
            "Semgrep analysis finished: findings=%d exit_code=%s "
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


def _map_results(
    report: _SemgrepReport, repo_dir: str, targets: list[str]
) -> list[StaticAnalysisFinding]:
    findings: list[StaticAnalysisFinding] = []
    for result in report.results:
        if not result.check_id.strip() or not result.extra.message.strip():
            raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)

        severity = _SEVERITY_MAP.get(result.extra.severity)
        if severity is None:
            raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)

        file_path = map_output_path(
            result.path, repo_dir, targets, fold_case=True
        )
        if file_path is None:
            raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)

        end_line = _end_line_for(result)

        try:
            finding = StaticAnalysisFinding(
                tool=_TOOL,
                rule_id=result.check_id,
                category=_category_for(result),
                severity=severity,
                message=result.extra.message,
                file_path=file_path,
                start_line=result.start.line,
                end_line=end_line,
            )
        except ValidationError:
            raise _OutputError(
                StaticAnalysisErrorCode.SCHEMA_MISMATCH
            ) from None
        findings.append(finding)

    return findings


def _end_line_for(result: _SemgrepResult) -> int:
    if result.end is None:
        return result.start.line
    if result.end.line < result.start.line:
        raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)
    return result.end.line


def _category_for(result: _SemgrepResult) -> Category:
    metadata = result.extra.metadata
    if isinstance(metadata, dict):
        category = metadata.get("category")
        if isinstance(category, str):
            mapped = _CATEGORY_BY_NAME.get(category.strip().lower())
            if mapped is not None:
                return mapped
    for segment in result.check_id.split("."):
        mapped = _CATEGORY_BY_NAME.get(segment.strip().lower())
        if mapped is not None:
            return mapped
    return Category.QUALITY


def _scanned_keys(report: _SemgrepReport, repo_dir: str) -> set[str]:
    keys: set[str] = set()
    for entry in report.paths.scanned:
        normalized = normalize_output_path(entry, repo_dir)
        if normalized is None:
            raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)
        keys.add(os.path.normcase(normalized))
    return keys


def _covers_targets(scanned: set[str], targets: list[str]) -> bool:
    expected = {os.path.normcase(target) for target in targets}
    return expected <= scanned


def _validate_config_path(config_path: str) -> str:
    if (
        not isinstance(config_path, str)
        or not config_path.strip()
        or config_path != config_path.strip()
    ):
        raise ValueError("config_path must be a non-empty path")
    if "\x00" in config_path:
        raise ValueError("config_path must not contain NUL")
    resolved = os.path.realpath(config_path)
    if not os.path.isfile(resolved):
        raise ValueError("config_path must be an existing file")
    return resolved