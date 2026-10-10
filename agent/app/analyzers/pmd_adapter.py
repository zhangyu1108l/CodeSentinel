"""PMD static analysis adapter (Phase 7.6).

Runs PMD 7.x in JSON output mode through the Phase 7.2 ToolRunner and maps
its rule violations onto the Phase 7.1 contract. Only the caller supplied
repository directory and Java file paths are ever scanned: directories are
never handed to PMD, so the adapter cannot recursively scan the reviewed
repository on its own.

Command form (verified against the locally installed PMD 7.28.0
distribution; its own launcher script was read to confirm the entry class
and the classpath layout):

    java -cp "<pmd_home>/conf<pathsep><pmd_home>/lib/*"
        net.sourceforge.pmd.cli.PmdCli check
        --no-cache --no-progress --format=json
        --rulesets=<ref> [--rulesets=<ref>...]
        --dir=<file> [--dir=<file>...]

PMD is launched through java directly instead of pmd.bat on purpose: on
Windows a batch launcher is executed through the system command
processor, which re-parses its arguments, so a target file whose name
contains cmd metacharacters ('&', '|', '^', '%', ...) could execute
arbitrary commands. A direct java.exe launch has no shell in between, so
untrusted file names stay inert data. The java executable itself is
resolved the same way the executor resolves it (PATH lookup for a bare
name, realpath for an explicit path) and a resolved batch launcher is
rejected, so a java.bat shadowing java.exe on PATH cannot bypass the
check. The command is always an argument list; shell=True is never used.

Every option value is attached with '=' so a target file whose name starts
with '-' can never be parsed as an option. --no-cache keeps the workspace
free of a PMD cache, and --no-progress keeps stdout free of progress
noise. The report stays on stdout; PMD logs go to stderr (its documented
slf4j-simple behaviour), so --report-file is deliberately not used.
--no-fail-on-violation and --no-fail-on-error are also deliberately not
used: exit codes 4 (violations) and 5 (recoverable errors) must stay
observable.

Ruleset policy:

- Rulesets are explicitly supplied by the trusted caller. A reference is
  either a bundled classpath reference (''category/...xml'' or
  ''rulesets/...xml'' shipped with the PMD distribution) or an existing
  file outside the reviewed repository. URLs (http, https, file) are
  rejected, so no rule is ever downloaded, and a ruleset that resolves
  inside the reviewed repository is rejected at run time.

Target policy:

- Only explicit repository relative .java files are accepted, matching the
  project's Java review scope; no suffix guessing and no directory scans.

PMD home policy:

- pmd_home points at the extracted PMD 7.x distribution and is validated
  once: it must be a directory with ''conf'' and ''lib'' subdirectories
  and lib must contain at least one jar. The classpath is
  ''<pmd_home>/conf'' joined with ''<pmd_home>/lib/*'' using os.pathsep,
  matching the layout the distribution's own launcher uses; the JVM
  expands the wildcard at startup.

Exit status (PMD 7.3.0+): 0 clean, 4 violations found, 1 exception,
2 usage error, 5 recoverable error (possible false negatives). 0 and 4 are
accepted and the JSON decides what was found; 1, 2 and 5 become
ERROR / PROCESS_FAILED.

Mapping policy:

- rule_id is the PMD rule name; message is the violation description.
  priority maps explicitly onto severity: 1 -> HIGH, 2 -> MEDIUM,
  3 -> MEDIUM, 4 -> LOW, 5 -> INFO. This translates the tool's priority,
  it is not a final risk verdict; the Validator may adjust it.
- Category derives from the ruleset name (Error Prone / Multithreading ->
  BUG, Security -> SECURITY, Performance -> PERFORMANCE, Best Practices /
  Code Style / Design / Documentation -> QUALITY); a missing or
  unrecognized ruleset falls back to QUALITY, never assumed to be a
  security issue.
- beginline is start_line; endline is end_line when present, otherwise
  start_line. Missing or contradictory line data invalidates the run
  instead of fabricating a location.
- A non empty processingErrors or configurationErrors array means the scan
  was incomplete: the run becomes ERROR / PROCESS_FAILED with no findings.
  Suppressed violations are ignored (the analyzed code suppressed them).
- A truncated stdout, empty output, invalid JSON or any unmappable file or
  violation invalidates the whole run (PARSE_ERROR, no findings). A
  truncated stderr alone does not affect the JSON result.
- Reported file paths are normalized to repository relative forward slash
  paths and must belong to the requested target set.

Logs never contain stdout, stderr, messages or source code; failures are
reported only through finite StaticAnalysisErrorCode values.
"""

import logging
import os
import shutil
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.analyzers.execution import ExecutionStatus
from app.analyzers.json_output import JsonStatus, parse_json_output
from app.analyzers.path_guard import (
    is_within,
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

logger = logging.getLogger("codesentinel-ai.pmd_adapter")

DEFAULT_JAVA_EXECUTABLE = "java"
PMD_MAIN_CLASS = "net.sourceforge.pmd.cli.PmdCli"

_TOOL = StaticAnalysisTool.PMD
_ALLOWED_SUFFIXES = (".java",)
_ACCEPTED_EXIT_CODES = frozenset({0, 4})
_BUILTIN_RULESET_PREFIXES = ("category/", "rulesets/")
_URL_PREFIXES = ("http://", "https://", "file://")
_BATCH_LAUNCHER_SUFFIXES = (".bat", ".cmd")

_SEVERITY_BY_PRIORITY = {
    1: Severity.HIGH,
    2: Severity.MEDIUM,
    3: Severity.MEDIUM,
    4: Severity.LOW,
    5: Severity.INFO,
}

_CATEGORY_BY_RULESET = {
    "best practices": Category.QUALITY,
    "code style": Category.QUALITY,
    "design": Category.QUALITY,
    "documentation": Category.QUALITY,
    "error prone": Category.BUG,
    "multithreading": Category.BUG,
    "performance": Category.PERFORMANCE,
    "security": Category.SECURITY,
}

_EXECUTION_STATUS_MAP = {
    ExecutionStatus.UNAVAILABLE: StaticAnalysisStatus.UNAVAILABLE,
    ExecutionStatus.TIMEOUT: StaticAnalysisStatus.TIMEOUT,
    ExecutionStatus.ERROR: StaticAnalysisStatus.ERROR,
}


class _PmdViolation(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    beginline: int = Field(ge=1)
    endline: int | None = Field(default=None, ge=1)
    description: str
    rule: str
    ruleset: str | None = None
    priority: int = Field(ge=1, le=5)


class _PmdFile(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    filename: str
    violations: list[_PmdViolation]


class _PmdReport(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    files: list[_PmdFile]
    suppressedViolations: list
    processingErrors: list
    configurationErrors: list


class _OutputError(Exception):
    """Unmappable tool output; carries only a safe error code."""

    def __init__(self, error_code: StaticAnalysisErrorCode):
        super().__init__(error_code.value)
        self.error_code = error_code


class PMDAdapter:
    """Maps one bounded PMD run onto the static analysis contract."""

    def __init__(
        self,
        runner: ToolRunner,
        rulesets: Sequence[str],
        pmd_home: str,
        java_executable: str = DEFAULT_JAVA_EXECUTABLE,
    ):
        self.runner = runner
        self.rulesets = _validate_rulesets(rulesets)
        self.pmd_home = _validate_pmd_home(pmd_home)
        self.java_executable = _resolve_java_launcher(java_executable)

    def analyze(
        self, repo_dir: str, file_paths: Sequence[str]
    ) -> StaticAnalysisResult:
        """Check the given repository relative Java files.

        repo_dir must be an existing directory; every target must be a
        repository relative .java file that exists inside repo_dir. File
        based rulesets must not live inside the reviewed repository.
        Invalid input raises ValueError (a caller defect), while every
        tool level failure degrades into a StaticAnalysisResult instead.
        """
        root = validate_repo_dir(repo_dir)
        for ruleset in self.rulesets:
            if ruleset.startswith(_BUILTIN_RULESET_PREFIXES):
                continue
            if is_within(root, ruleset):
                raise ValueError(
                    "pmd ruleset files must not live inside the reviewed "
                    "repository"
                )
        targets = validate_targets(
            root, file_paths, suffixes=_ALLOWED_SUFFIXES
        )

        classpath = os.pathsep.join(
            [
                os.path.join(self.pmd_home, "conf"),
                os.path.join(self.pmd_home, "lib", "*"),
            ]
        )
        command = [
            self.java_executable,
            "-cp",
            classpath,
            PMD_MAIN_CLASS,
            "check",
            "--no-cache",
            "--no-progress",
            "--format=json",
            *[f"--rulesets={ruleset}" for ruleset in self.rulesets],
            *[f"--dir={target}" for target in targets],
        ]
        logger.debug(
            "Running PMD on %d target file(s)", len(targets)
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
                "PMD run failed: exit_code=%s", execution.exit_code
            )
            return _failure(
                execution,
                StaticAnalysisStatus.ERROR,
                StaticAnalysisErrorCode.PROCESS_FAILED,
            )

        if execution.stdout_truncated:
            logger.warning(
                "PMD stdout was truncated; result rejected"
            )
            return _failure(
                execution,
                StaticAnalysisStatus.PARSE_ERROR,
                StaticAnalysisErrorCode.INVALID_OUTPUT,
            )

        parsed = parse_json_output(execution.stdout)
        if parsed.status != JsonStatus.VALID:
            logger.warning(
                "PMD output is not valid JSON: json_status=%s",
                parsed.status.value,
            )
            return _failure(
                execution,
                StaticAnalysisStatus.PARSE_ERROR,
                StaticAnalysisErrorCode.INVALID_OUTPUT,
            )

        try:
            report = _PmdReport.model_validate(parsed.data)
        except ValidationError:
            logger.warning("PMD output structure rejected")
            return _failure(
                execution,
                StaticAnalysisStatus.PARSE_ERROR,
                StaticAnalysisErrorCode.SCHEMA_MISMATCH,
            )

        if report.processingErrors or report.configurationErrors:
            logger.warning(
                "PMD reported processing or configuration errors; "
                "result rejected"
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
                "PMD output rejected: error_code=%s",
                error.error_code.value,
            )
            return _failure(
                execution, StaticAnalysisStatus.PARSE_ERROR, error.error_code
            )

        logger.debug(
            "PMD analysis finished: findings=%d exit_code=%s "
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
    report: _PmdReport, repo_dir: str, targets: list[str]
) -> list[StaticAnalysisFinding]:
    allowed = set(targets)
    findings: list[StaticAnalysisFinding] = []
    for pmd_file in report.files:
        file_path = map_output_path(pmd_file.filename, repo_dir, allowed)
        if file_path is None:
            raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)
        for violation in pmd_file.violations:
            if (
                not violation.rule.strip()
                or not violation.description.strip()
            ):
                raise _OutputError(
                    StaticAnalysisErrorCode.SCHEMA_MISMATCH
                )
            if violation.ruleset is not None and not (
                violation.ruleset.strip()
            ):
                raise _OutputError(
                    StaticAnalysisErrorCode.SCHEMA_MISMATCH
                )

            end_line = _end_line_for(violation)

            try:
                finding = StaticAnalysisFinding(
                    tool=_TOOL,
                    rule_id=violation.rule,
                    category=_category_for(violation),
                    severity=_SEVERITY_BY_PRIORITY[violation.priority],
                    message=violation.description,
                    file_path=file_path,
                    start_line=violation.beginline,
                    end_line=end_line,
                )
            except ValidationError:
                raise _OutputError(
                    StaticAnalysisErrorCode.SCHEMA_MISMATCH
                ) from None
            findings.append(finding)

    return findings


def _end_line_for(violation: _PmdViolation) -> int:
    if violation.endline is None:
        return violation.beginline
    if violation.endline < violation.beginline:
        raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)
    return violation.endline


def _category_for(violation: _PmdViolation) -> Category:
    if violation.ruleset is None:
        return Category.QUALITY
    return _CATEGORY_BY_RULESET.get(
        violation.ruleset.strip().lower(), Category.QUALITY
    )


def _validate_rulesets(rulesets: Sequence[str]) -> list[str]:
    if rulesets is None or isinstance(rulesets, (str, bytes)):
        raise ValueError(
            "rulesets must be a sequence of references, not a string"
        )
    validated: list[str] = []
    for reference in rulesets:
        validated.append(_validate_ruleset(reference))
    if not validated:
        raise ValueError("at least one ruleset is required")
    return validated


def _validate_ruleset(reference: str) -> str:
    if (
        not isinstance(reference, str)
        or not reference.strip()
        or reference != reference.strip()
    ):
        raise ValueError("ruleset reference must be a non-empty string")
    if "\x00" in reference:
        raise ValueError("ruleset reference must not contain NUL")
    if reference.lower().startswith(_URL_PREFIXES):
        raise ValueError("ruleset URLs are not allowed")
    if reference.startswith(_BUILTIN_RULESET_PREFIXES) and (
        reference.endswith(".xml")
    ):
        return reference
    resolved = os.path.realpath(reference)
    if not os.path.isfile(resolved):
        raise ValueError("ruleset file must be an existing file")
    return resolved


def _validate_pmd_home(pmd_home: str) -> str:
    """Validate a PMD distribution root and return its real path.

    The distribution layout is required: ''conf'' (logging configuration)
    and ''lib'' with at least one jar. Failing fast here turns a broken
    deployment into a clear caller error instead of a confusing JVM
    startup failure.
    """
    if (
        not isinstance(pmd_home, str)
        or not pmd_home.strip()
        or pmd_home != pmd_home.strip()
    ):
        raise ValueError("pmd_home must be a non-empty path")
    if "\x00" in pmd_home:
        raise ValueError("pmd_home must not contain NUL")
    root = os.path.realpath(pmd_home)
    if not os.path.isdir(root):
        raise ValueError("pmd_home must be an existing directory")
    if not os.path.isdir(os.path.join(root, "conf")):
        raise ValueError("pmd_home must contain a conf directory")
    lib = os.path.join(root, "lib")
    if not os.path.isdir(lib):
        raise ValueError("pmd_home must contain a lib directory")
    try:
        entries = os.listdir(lib)
    except OSError:
        raise ValueError("pmd_home lib directory cannot be read") from None
    if not any(entry.lower().endswith(".jar") for entry in entries):
        raise ValueError(
            "pmd_home lib directory must contain at least one jar"
        )
    return root


def _resolve_java_launcher(java_executable: str) -> str:
    """Resolve and validate the Java launcher, returning its real path.

    The launcher is resolved exactly like the executor will resolve it
    (PATH lookup for a bare name, realpath for an explicit path) and the
    resolved target is checked for a batch suffix. Checking only the
    caller supplied string would let a java.bat earlier on PATH through,
    and launching through a batch file re-introduces the command
    processor argument parsing this adapter exists to avoid.
    """
    if (
        not isinstance(java_executable, str)
        or not java_executable.strip()
        or java_executable != java_executable.strip()
    ):
        raise ValueError("java executable must be a non-empty string")
    if "\x00" in java_executable:
        raise ValueError("java executable must not contain NUL")
    if os.path.sep in java_executable or (
        os.path.altsep is not None and os.path.altsep in java_executable
    ):
        resolved = os.path.realpath(java_executable)
    else:
        found = shutil.which(java_executable)
        resolved = os.path.realpath(found) if found else None
    if resolved is None:
        raise ValueError("java executable was not found")
    if resolved.lower().endswith(_BATCH_LAUNCHER_SUFFIXES):
        raise ValueError(
            "batch java launchers are not allowed; use java.exe"
        )
    if not os.path.isfile(resolved):
        raise ValueError("java executable must be an existing file")
    return resolved