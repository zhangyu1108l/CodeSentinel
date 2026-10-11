"""Bandit static security adapter (Phase 7.4).

Runs Bandit in JSON output mode through the Phase 7.2 ToolRunner and maps
its security issues onto the Phase 7.1 contract. Only the caller supplied
repository directory and Python file paths are ever checked.

Command form:

    bandit -f json <files...>

run with cwd set to the repository directory and relative file arguments.
-r is deliberately absent: directories are never scanned, and Bandit only
auto-discovers a repository .bandit ini file when invoked with -r, so the
reviewed repository cannot change tool behaviour through configuration.
--exit-zero is also absent because exit code 1 must stay observable.

Mapping policy:

- Every Bandit issue is SECURITY; rule_id is the Bandit test id; message
  is issue_text. issue_severity maps 1:1 onto Severity (LOW, MEDIUM,
  HIGH); this reflects the tool's own classification and is not a claim
  about the final vulnerability risk, which the Validator may adjust.
  issue_confidence is validated but never stored or mapped: the Phase
  7.1 finding has no confidence field, and tool confidence is a different
  metric than validated finding confidence.
- start_line is line_number; end_line is max(line_range) when Bandit
  provides a usable span, otherwise line_number. A span is never invented
  and a contradictory span (end before start) invalidates the run.
- Exit codes 0 (no issues) and 1 (issues found) are accepted regardless
  of whether results are present. Any other completed exit code becomes
  ERROR / PROCESS_FAILED.
- A non empty Bandit errors list means part of the scan could not be
  analysed; the run becomes ERROR / PROCESS_FAILED with no findings, so
  a partial scan never masquerades as a complete one.
- A truncated stdout, empty output, invalid JSON, wrong structure or any
  unmappable issue invalidates the whole run (PARSE_ERROR, no findings).
  A truncated stderr alone does not affect the JSON result.
- Issue filenames are normalized to repository relative forward slash
  paths that must resolve inside the repository directory and belong to
  the requested target set. The path guard is shared with the Ruff
  adapter so both tools enforce exactly the same rules.

Logs never contain stdout, stderr, issue text or source code; failures
are reported only through finite StaticAnalysisErrorCode values.
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
from app.analyzers.ruff_adapter import _OutputError
from app.analyzers.tool_runner import ToolRunner
from app.schemas.review import Category, Severity
from app.schemas.static_analysis import (
    StaticAnalysisErrorCode,
    StaticAnalysisFinding,
    StaticAnalysisResult,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)

logger = logging.getLogger("codesentinel-ai.bandit_adapter")

BANDIT_EXECUTABLE = "bandit"

_TOOL = StaticAnalysisTool.BANDIT
_CATEGORY = Category.SECURITY
_ACCEPTED_EXIT_CODES = frozenset({0, 1})
_ALLOWED_SUFFIXES = (".py", ".pyi")
_CONFIDENCE_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH"})

_SEVERITY_MAP = {
    "LOW": Severity.LOW,
    "MEDIUM": Severity.MEDIUM,
    "HIGH": Severity.HIGH,
}

_EXECUTION_STATUS_MAP = {
    ExecutionStatus.UNAVAILABLE: StaticAnalysisStatus.UNAVAILABLE,
    ExecutionStatus.TIMEOUT: StaticAnalysisStatus.TIMEOUT,
    ExecutionStatus.ERROR: StaticAnalysisStatus.ERROR,
}


class _BanditIssue(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    test_id: str
    issue_text: str
    filename: str
    line_number: int = Field(ge=1)
    issue_severity: str
    issue_confidence: str
    line_range: list[int] | None = None


class _BanditReport(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    errors: list
    results: list[_BanditIssue]


class BanditAdapter:
    """Maps one bounded Bandit run onto the static analysis contract."""

    def __init__(
        self, runner: ToolRunner, executable: str = BANDIT_EXECUTABLE
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
        """Scan the given repository relative Python files.

        repo_dir must be an existing directory; every target must be a
        repository relative .py / .pyi file that exists inside repo_dir.
        Invalid input raises ValueError (a caller defect), while every
        tool level failure degrades into a StaticAnalysisResult instead.
        """
        root = validate_repo_dir(repo_dir)
        targets = validate_targets(
            root, file_paths, suffixes=_ALLOWED_SUFFIXES
        )

        command = [self.executable, "-f", "json", *targets]
        logger.debug(
            "Running Bandit on %d target file(s)", len(targets)
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
                "Bandit run failed: exit_code=%s", execution.exit_code
            )
            return _failure(
                execution,
                StaticAnalysisStatus.ERROR,
                StaticAnalysisErrorCode.PROCESS_FAILED,
            )

        if execution.stdout_truncated:
            logger.warning(
                "Bandit stdout was truncated; result rejected"
            )
            return _failure(
                execution,
                StaticAnalysisStatus.PARSE_ERROR,
                StaticAnalysisErrorCode.INVALID_OUTPUT,
            )

        parsed = parse_json_output(execution.stdout)
        if parsed.status != JsonStatus.VALID:
            logger.warning(
                "Bandit output is not valid JSON: json_status=%s",
                parsed.status.value,
            )
            return _failure(
                execution,
                StaticAnalysisStatus.PARSE_ERROR,
                StaticAnalysisErrorCode.INVALID_OUTPUT,
            )

        try:
            report = _BanditReport.model_validate(parsed.data)
        except ValidationError:
            logger.warning("Bandit output structure rejected")
            return _failure(
                execution,
                StaticAnalysisStatus.PARSE_ERROR,
                StaticAnalysisErrorCode.SCHEMA_MISMATCH,
            )

        if report.errors:
            logger.warning(
                "Bandit reported scan errors; result rejected"
            )
            return _failure(
                execution,
                StaticAnalysisStatus.ERROR,
                StaticAnalysisErrorCode.PROCESS_FAILED,
            )

        try:
            findings = _map_report(report, repo_dir, targets)
        except _OutputError as error:
            logger.warning(
                "Bandit output rejected: error_code=%s",
                error.error_code.value,
            )
            return _failure(
                execution, StaticAnalysisStatus.PARSE_ERROR, error.error_code
            )

        logger.debug(
            "Bandit analysis finished: findings=%d exit_code=%s "
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


def _map_report(
    report: _BanditReport, repo_dir: str, targets: list[str]
) -> list[StaticAnalysisFinding]:
    allowed = set(targets)
    findings: list[StaticAnalysisFinding] = []
    for issue in report.results:
        if not issue.test_id.strip() or not issue.issue_text.strip():
            raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)

        severity = _SEVERITY_MAP.get(issue.issue_severity)
        if severity is None:
            raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)

        if issue.issue_confidence not in _CONFIDENCE_LEVELS:
            raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)

        file_path = map_output_path(issue.filename, repo_dir, allowed)
        if file_path is None:
            raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)

        end_line = _end_line_for(issue)

        try:
            finding = StaticAnalysisFinding(
                tool=_TOOL,
                rule_id=issue.test_id,
                category=_CATEGORY,
                severity=severity,
                message=issue.issue_text,
                file_path=file_path,
                start_line=issue.line_number,
                end_line=end_line,
            )
        except ValidationError:
            raise _OutputError(
                StaticAnalysisErrorCode.SCHEMA_MISMATCH
            ) from None
        findings.append(finding)

    return findings


def _end_line_for(issue: _BanditIssue) -> int:
    if not issue.line_range:
        return issue.line_number
    if any(line < 1 for line in issue.line_range):
        raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)
    end_line = max(issue.line_range)
    if end_line < issue.line_number:
        raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)
    return end_line