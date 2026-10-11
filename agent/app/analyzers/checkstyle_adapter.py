"""Checkstyle static analysis adapter (Phase 7.7.1).

Runs Checkstyle with its XML report through the Phase 7.2 ToolRunner and
maps its violations onto the Phase 7.1 contract. Only the caller supplied
repository directory and Java file paths are ever scanned: directories are
never handed to Checkstyle, so the adapter cannot recursively scan the
reviewed repository on its own.

Command form (verified against the Checkstyle 14.3.0 command line docs):

    java -jar <checkstyle-all.jar> -c <config> -f xml <files...>

Checkstyle has no JSON renderer (the valid formats are xml, sarif and
plain), so the XML report is parsed with the standard library XML parser.
The report is located inside stdout instead of parsing stdout as a whole,
so surrounding text cannot break the parse; 14.3.0 writes a pure XML
document to stdout and its localized ''Checkstyle ends with N errors.''
summary to stderr, which is never parsed for findings.

Checkstyle is launched through java directly (never checkstyle.bat), for
the same reason as the PMD adapter: on Windows a batch launcher is
executed through the system command processor, which re-parses its
arguments, so untrusted file names could execute commands. The java
executable is resolved and validated like the executor resolves it, and a
resolved batch launcher is rejected. The command is always an argument
list; shell=True is never used.

Checkstyle's CLI is picocli based and enables AtFiles expansion, so a
target file name starting with ''-'' or ''@'' could be parsed as an
option or as an argument file. Such targets are rejected instead of
being passed through.

Config policy:

- config is explicitly supplied by the trusted caller. A reference is
  either a configuration bundled inside the checkstyle jar
  (''google_checks.xml'' / ''sun_checks.xml'', with or without a leading
  slash) or an existing file outside the reviewed repository. URLs
  (http, https, file) are rejected, so no rule is ever downloaded, and a
  config that resolves inside the reviewed repository is rejected at run
  time.

Jar policy:

- checkstyle_jar must be an existing .jar file; the runnable distribution
  is the ''checkstyle-<version>-all.jar'' (the plain jar has no bundled
  dependencies and no Main-Class), which is the deployment assumption
  recorded for the real integration step.

Exit status (verified against 14.3.0 at the real integration step):
Checkstyle reports the error-severity violation count in the exit code
(warnings do not count, so a report with only warnings still exits 0) and
uses a negative code on failures (0xFFFFFFFE on Windows), so no
exit-code whitelist is applied. A complete, parseable XML report decides
what was found (status OK, even with a non zero exit code); when no
usable report exists, a non zero exit code becomes ERROR /
PROCESS_FAILED and a zero exit code becomes PARSE_ERROR /
INVALID_OUTPUT, so a failed run is never mistaken for a clean run.

Mapping policy:

- rule_id is the report ''source'' (the check's fully qualified class
  name, for example
  com.puppycrawl.tools.checkstyle.checks.coding.FallThroughCheck);
  message is the report message. severity maps explicitly:
  error -> HIGH, warning -> MEDIUM, info -> LOW. This translates the
  tool's own severity, it is not a final risk verdict.
- Category derives from the check package: ''checks.coding'' -> BUG;
  every other core package (javadoc, whitespace, naming, imports, sizes,
  blocks, design, metrics, ...) and any unknown package fall back to
  QUALITY, because Checkstyle is a style tool and no finding is assumed
  to be a security or performance issue without evidence.
- start_line is the report line; Checkstyle does not report an end line,
  so end_line equals start_line (a span is never invented). Missing or
  invalid line data invalidates the run.
- Reported file paths are normalized to repository relative forward slash
  paths and must belong to the requested target set.

Logs never contain stdout, stderr, messages or source code; failures are
reported only through finite StaticAnalysisErrorCode values.
"""

import logging
import os
import xml.etree.ElementTree as ET
from collections.abc import Sequence

from app.analyzers.execution import ExecutionStatus
from app.analyzers.path_guard import (
    is_within,
    map_output_path,
    validate_repo_dir,
    validate_targets,
)
from app.analyzers.pmd_adapter import _resolve_java_launcher
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

logger = logging.getLogger("codesentinel-ai.checkstyle_adapter")

DEFAULT_JAVA_EXECUTABLE = "java"

_TOOL = StaticAnalysisTool.CHECKSTYLE
_ALLOWED_SUFFIXES = (".java",)
_BUILTIN_CONFIG_NAMES = frozenset(
    {
        "google_checks.xml",
        "/google_checks.xml",
        "sun_checks.xml",
        "/sun_checks.xml",
    }
)
_URL_PREFIXES = ("http://", "https://", "file://")
_OPTION_LIKE_PREFIXES = ("-", "@")

_XML_ROOT_TAG = "checkstyle"
_XML_FILE_TAG = "file"
_XML_ERROR_TAG = "error"
_XML_ROOT_CLOSE = "</checkstyle>"

_SEVERITY_MAP = {
    "error": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "info": Severity.LOW,
}

_CATEGORY_BY_PACKAGE = {
    "coding": Category.BUG,
}

_EXECUTION_STATUS_MAP = {
    ExecutionStatus.UNAVAILABLE: StaticAnalysisStatus.UNAVAILABLE,
    ExecutionStatus.TIMEOUT: StaticAnalysisStatus.TIMEOUT,
    ExecutionStatus.ERROR: StaticAnalysisStatus.ERROR,
}


class CheckstyleAdapter:
    """Maps one bounded Checkstyle run onto the static analysis contract."""

    def __init__(
        self,
        runner: ToolRunner,
        config: str,
        checkstyle_jar: str,
        java_executable: str = DEFAULT_JAVA_EXECUTABLE,
    ):
        self.runner = runner
        self.config = _validate_config(config)
        self.checkstyle_jar = _validate_checkstyle_jar(checkstyle_jar)
        self.java_executable = _resolve_java_launcher(java_executable)

    def analyze(
        self, repo_dir: str, file_paths: Sequence[str]
    ) -> StaticAnalysisResult:
        """Check the given repository relative Java files.

        repo_dir must be an existing directory; every target must be a
        repository relative .java file that exists inside repo_dir, and
        its name must not start with '-' or '@' because the Checkstyle
        CLI would parse such a token as an option or an argument file.
        File based configs must not live inside the reviewed repository.
        Invalid input raises ValueError (a caller defect), while every
        tool level failure degrades into a StaticAnalysisResult instead.
        """
        root = validate_repo_dir(repo_dir)
        if (
            self.config not in _BUILTIN_CONFIG_NAMES
            and is_within(root, self.config)
        ):
            raise ValueError(
                "checkstyle config must not live inside the reviewed "
                "repository"
            )
        targets = validate_targets(
            root, file_paths, suffixes=_ALLOWED_SUFFIXES
        )
        for target in targets:
            if target.startswith(_OPTION_LIKE_PREFIXES):
                raise ValueError(
                    "target file names starting with '-' or '@' are not "
                    "supported by the checkstyle CLI"
                )

        command = [
            self.java_executable,
            "-jar",
            self.checkstyle_jar,
            "-c",
            self.config,
            "-f",
            "xml",
            *targets,
        ]
        logger.debug(
            "Running Checkstyle on %d target file(s)", len(targets)
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

        if execution.stdout_truncated:
            logger.warning(
                "Checkstyle stdout was truncated; result rejected"
            )
            return _failure(
                execution,
                StaticAnalysisStatus.PARSE_ERROR,
                StaticAnalysisErrorCode.INVALID_OUTPUT,
            )

        try:
            document = _extract_checkstyle_document(execution.stdout)
        except _OutputError as error:
            if execution.exit_code not in (0, None):
                logger.warning(
                    "Checkstyle produced no usable report: exit_code=%s",
                    execution.exit_code,
                )
                return _failure(
                    execution,
                    StaticAnalysisStatus.ERROR,
                    StaticAnalysisErrorCode.PROCESS_FAILED,
                )
            logger.warning(
                "Checkstyle output rejected: error_code=%s",
                error.error_code.value,
            )
            return _failure(
                execution, StaticAnalysisStatus.PARSE_ERROR, error.error_code
            )

        try:
            findings = _map_report(document, repo_dir, targets)
        except _OutputError as error:
            logger.warning(
                "Checkstyle output rejected: error_code=%s",
                error.error_code.value,
            )
            return _failure(
                execution, StaticAnalysisStatus.PARSE_ERROR, error.error_code
            )

        logger.debug(
            "Checkstyle analysis finished: findings=%d exit_code=%s "
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


def _extract_checkstyle_document(stdout: str) -> ET.Element:
    """Extract and parse the checkstyle XML report from stdout.

    The CLI appends its summary line after the report, so the document is
    located between the root open and close markers instead of parsing
    stdout as a whole. Only the document is parsed; the surrounding text
    is ignored on purpose.
    """
    text = stdout.strip() if stdout else ""
    start = text.find("<checkstyle")
    if start < 0:
        raise _OutputError(StaticAnalysisErrorCode.INVALID_OUTPUT)
    end_marker = text.find(_XML_ROOT_CLOSE, start)
    if end_marker >= 0:
        document = text[start:end_marker + len(_XML_ROOT_CLOSE)]
    else:
        end_of_tag = text.find(">", start)
        if end_of_tag < 0 or text[end_of_tag - 1] != "/":
            raise _OutputError(StaticAnalysisErrorCode.INVALID_OUTPUT)
        document = text[start:end_of_tag + 1]
    try:
        root = ET.fromstring(document)
    except ET.ParseError:
        raise _OutputError(
            StaticAnalysisErrorCode.INVALID_OUTPUT
        ) from None
    if root.tag != _XML_ROOT_TAG:
        raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)
    return root


def _map_report(
    root: ET.Element, repo_dir: str, targets: list[str]
) -> list[StaticAnalysisFinding]:
    allowed = set(targets)
    findings: list[StaticAnalysisFinding] = []
    for file_element in root:
        if file_element.tag != _XML_FILE_TAG:
            raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)
        name = file_element.get("name")
        if name is None:
            raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)
        file_path = map_output_path(name, repo_dir, allowed)
        if file_path is None:
            raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)
        for error_element in file_element:
            if error_element.tag != _XML_ERROR_TAG:
                raise _OutputError(
                    StaticAnalysisErrorCode.SCHEMA_MISMATCH
                )
            findings.append(_map_error(error_element, file_path))
    return findings


def _map_error(
    element: ET.Element, file_path: str
) -> StaticAnalysisFinding:
    severity = _SEVERITY_MAP.get(element.get("severity"))
    if severity is None:
        raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)

    message = element.get("message")
    if message is None or not message.strip():
        raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)

    source = element.get("source")
    if source is None or not source.strip():
        raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)

    line = _parse_line(element.get("line"))

    return StaticAnalysisFinding(
        tool=_TOOL,
        rule_id=source,
        category=_category_for(source),
        severity=severity,
        message=message,
        file_path=file_path,
        start_line=line,
        end_line=line,
    )


def _parse_line(value: str | None) -> int:
    if value is None:
        raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)
    try:
        line = int(value.strip())
    except (TypeError, ValueError):
        raise _OutputError(
            StaticAnalysisErrorCode.SCHEMA_MISMATCH
        ) from None
    if line < 1:
        raise _OutputError(StaticAnalysisErrorCode.SCHEMA_MISMATCH)
    return line


def _category_for(source: str) -> Category:
    parts = source.split(".")
    if "checks" in parts:
        index = parts.index("checks")
        if index + 1 < len(parts):
            return _CATEGORY_BY_PACKAGE.get(
                parts[index + 1], Category.QUALITY
            )
    return Category.QUALITY


def _validate_config(config: str) -> str:
    if (
        not isinstance(config, str)
        or not config.strip()
        or config != config.strip()
    ):
        raise ValueError("config must be a non-empty string")
    if "\x00" in config:
        raise ValueError("config must not contain NUL")
    if config.lower().startswith(_URL_PREFIXES):
        raise ValueError("config URLs are not allowed")
    if config in _BUILTIN_CONFIG_NAMES:
        return config
    resolved = os.path.realpath(config)
    if not os.path.isfile(resolved):
        raise ValueError("config file must be an existing file")
    return resolved


def _validate_checkstyle_jar(checkstyle_jar: str) -> str:
    if (
        not isinstance(checkstyle_jar, str)
        or not checkstyle_jar.strip()
        or checkstyle_jar != checkstyle_jar.strip()
    ):
        raise ValueError("checkstyle_jar must be a non-empty path")
    if "\x00" in checkstyle_jar:
        raise ValueError("checkstyle_jar must not contain NUL")
    resolved = os.path.realpath(checkstyle_jar)
    if not os.path.isfile(resolved):
        raise ValueError("checkstyle_jar must be an existing file")
    if not resolved.lower().endswith(".jar"):
        raise ValueError("checkstyle_jar must be a .jar file")
    return resolved