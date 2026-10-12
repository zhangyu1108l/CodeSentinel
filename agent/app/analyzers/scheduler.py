"""Serial static analysis scheduling over the Phase 7 adapters (Phase 8 prep).

The scheduler runs the registered analyzers one after another, never in
parallel, against a single repository directory and collects their Phase
7.1 StaticAnalysisResult values unchanged. It owns no analysis logic: the
adapters keep command construction, path validation, JSON/XML parsing and
status mapping, and the scheduler only selects applicable targets,
dispatches calls and records outcomes truthfully.

Truthfulness rules:

- Only tools whose configured suffix policy matches at least one target
  file are run. A tool with no applicable files is reported in
  skipped_tools and is neither a success nor a failure.
- A tool result is passed through unchanged; a failure status
  (UNAVAILABLE / TIMEOUT / ERROR / PARSE_ERROR) is never converted into
  success.
- An analyzer that raises, returns a non result object or returns a result
  for a different tool is recorded as ERROR / UNKNOWN for the registered
  tool, so one broken analyzer can neither abort the batch nor smuggle
  output in as a success.
- Input defects (missing repository directory, blank or non existing
  target paths) raise ValueError before any analyzer is called.

Target selection mirrors each adapter's own policy through
DEFAULT_SUFFIXES_BY_TOOL (Ruff and Bandit: .py/.pyi; PMD and Checkstyle:
.java; Semgrep: every provided file).

An optional per run budget (budget_seconds) bounds the whole batch: once
it is used up, applicable tools are recorded in budget_exhausted_tools
instead of being started. Per tool subprocess timeouts stay at the
adapter's local ToolRunner bound (60s default, 600s hard limit); the
batch budget only decides whether a tool may start.

Deliberately not implemented here: no ReviewService wiring, no LangGraph
integration, no cross service deadline headers, no source retrieval (use
MaterializedWorkspace or an existing checkout) and no result
deduplication.
"""

import logging
import math
import time
from collections.abc import Mapping, Sequence
from typing import Protocol

from pydantic import BaseModel, Field

from app.analyzers.path_guard import validate_repo_dir, validate_targets
from app.analyzers.workspace import MaterializedWorkspace
from app.schemas.static_analysis import (
    StaticAnalysisErrorCode,
    StaticAnalysisResult,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)

logger = logging.getLogger("codesentinel-ai.analyzer_scheduler")

DEFAULT_SUFFIXES_BY_TOOL: dict[StaticAnalysisTool, tuple[str, ...] | None] = {
    StaticAnalysisTool.RUFF: (".py", ".pyi"),
    StaticAnalysisTool.BANDIT: (".py", ".pyi"),
    StaticAnalysisTool.SEMGREP: None,
    StaticAnalysisTool.PMD: (".java",),
    StaticAnalysisTool.CHECKSTYLE: (".java",),
}


class StaticAnalyzer(Protocol):
    """One configured Phase 7 adapter, or a test double for it."""

    def analyze(
        self, repo_dir: str, file_paths: Sequence[str]
    ) -> StaticAnalysisResult:
        """Analyze the given repository relative files."""
        ...


class SchedulerOutcome(BaseModel):
    """Collection outcome: results, skipped tools and budget exhausted tools.

    skipped_tools had no applicable target files; budget_exhausted_tools
    were applicable but never started because the optional batch budget
    was used up. Neither list is a tool failure, but neither is a success.
    """

    results: list[StaticAnalysisResult] = Field(default_factory=list)
    skipped_tools: list[StaticAnalysisTool] = Field(default_factory=list)
    budget_exhausted_tools: list[StaticAnalysisTool] = Field(
        default_factory=list
    )


class StaticAnalysisScheduler:
    """Runs configured analyzers serially and collects their results.

    analyzers is a mapping of tool to a configured adapter and defines the
    execution order (mapping insertion order). suffixes optionally
    overrides the whole suffix policy: tools missing from an explicit
    mapping accept every provided file, and None always means "every
    file".
    """

    def __init__(
        self,
        analyzers: Mapping[StaticAnalysisTool, StaticAnalyzer],
        suffixes: (
            Mapping[StaticAnalysisTool, Sequence[str] | None] | None
        ) = None,
    ):
        if not isinstance(analyzers, Mapping):
            raise ValueError(
                "analyzers must be a mapping of tool to analyzer"
            )
        for tool, analyzer in analyzers.items():
            if not isinstance(tool, StaticAnalysisTool):
                raise ValueError(
                    "analyzer keys must be StaticAnalysisTool values"
                )
            if not callable(getattr(analyzer, "analyze", None)):
                raise ValueError(
                    "analyzer must provide analyze(): " + tool.value
                )
        self._analyzers = dict(analyzers)
        self._suffixes = _validate_suffixes(suffixes)

    def run(
        self,
        repo_dir: str,
        file_paths: Sequence[str],
        budget_seconds: float | None = None,
    ) -> SchedulerOutcome:
        """Analyze the given files with every applicable analyzer, serially.

        repo_dir must be an existing directory and every target must be an
        existing repository relative file; anything else raises ValueError
        before a single analyzer is called. An empty file list is a valid
        no-op and returns an empty outcome.

        budget_seconds optionally bounds the whole batch: once the budget
        is used up, applicable tools are recorded in budget_exhausted_tools
        instead of being started. Per tool subprocess timeouts remain the
        adapter's local ToolRunner bound; the batch budget governs whether
        a tool may start at all.
        """
        deadline = _deadline_for(budget_seconds)
        root = validate_repo_dir(repo_dir)
        targets = self._resolve_targets(root, file_paths)
        if not targets:
            logger.debug("No target files to analyze; nothing scheduled")
            return SchedulerOutcome()

        results: list[StaticAnalysisResult] = []
        skipped: list[StaticAnalysisTool] = []
        exhausted: list[StaticAnalysisTool] = []
        for tool, analyzer in self._analyzers.items():
            selected = _select_targets(
                targets, self._suffixes.get(tool)
            )
            if not selected:
                logger.debug(
                    "Skipping %s: no applicable target files", tool.value
                )
                skipped.append(tool)
                continue
            if deadline is not None and time.monotonic() >= deadline:
                logger.debug(
                    "Skipping %s: static analysis budget exhausted",
                    tool.value,
                )
                exhausted.append(tool)
                continue
            logger.debug(
                "Scheduling %s for %d target file(s)",
                tool.value,
                len(selected),
            )
            results.append(self._run_one(tool, analyzer, root, selected))

        logger.info(
            "Static analysis scheduling finished: tools_run=%d, "
            "skipped=%d, budget_exhausted=%d, findings=%d",
            len(results),
            len(skipped),
            len(exhausted),
            sum(len(result.findings) for result in results),
        )
        return SchedulerOutcome(
            results=results,
            skipped_tools=skipped,
            budget_exhausted_tools=exhausted,
        )

    def run_on_contents(
        self,
        files: Mapping[str, str],
        parent_dir: str | None = None,
        budget_seconds: float | None = None,
    ) -> SchedulerOutcome:
        """Materialize files into a temporary workspace, run, then clean up.

        The workspace is removed on success, on analyzer failure and on
        cancellation through the MaterializedWorkspace context manager.
        """
        with MaterializedWorkspace.create(
            files, parent_dir=parent_dir
        ) as workspace:
            return self.run(
                workspace.root,
                workspace.file_paths,
                budget_seconds=budget_seconds,
            )

    @staticmethod
    def _resolve_targets(
        root: str, file_paths: Sequence[str]
    ) -> list[str]:
        if file_paths is None or isinstance(file_paths, (str, bytes)):
            raise ValueError(
                "file_paths must be a sequence of paths, not a string"
            )
        try:
            targets = list(file_paths)
        except TypeError:
            raise ValueError(
                "file_paths must be a sequence of paths"
            ) from None
        if not targets:
            return []
        return validate_targets(root, targets)

    @staticmethod
    def _run_one(
        tool: StaticAnalysisTool,
        analyzer: StaticAnalyzer,
        repo_dir: str,
        targets: list[str],
    ) -> StaticAnalysisResult:
        try:
            result = analyzer.analyze(repo_dir, targets)
        except Exception as error:
            logger.warning(
                "Analyzer %s raised %s; recording ERROR result",
                tool.value,
                type(error).__name__,
            )
            return _error_result(tool)
        if not isinstance(result, StaticAnalysisResult):
            logger.warning(
                "Analyzer %s returned %s instead of a result; "
                "recording ERROR result",
                tool.value,
                type(result).__name__,
            )
            return _error_result(tool)
        if result.tool is not tool:
            logger.warning(
                "Analyzer %s returned a result for %s; "
                "recording ERROR result",
                tool.value,
                result.tool.value,
            )
            return _error_result(tool)
        return result


def _select_targets(
    targets: list[str], suffixes: Sequence[str] | None
) -> list[str]:
    if suffixes is None:
        return list(targets)
    allowed = tuple(suffixes)
    return [path for path in targets if path.endswith(allowed)]


def _validate_suffixes(
    suffixes: (
        Mapping[StaticAnalysisTool, Sequence[str] | None] | None
    ),
) -> dict[StaticAnalysisTool, tuple[str, ...] | None]:
    if suffixes is None:
        return dict(DEFAULT_SUFFIXES_BY_TOOL)
    if not isinstance(suffixes, Mapping):
        raise ValueError(
            "suffixes must be a mapping of tool to suffix policy"
        )
    validated: dict[StaticAnalysisTool, tuple[str, ...] | None] = {}
    for tool, policy in suffixes.items():
        if not isinstance(tool, StaticAnalysisTool):
            raise ValueError(
                "suffix policy keys must be StaticAnalysisTool values"
            )
        if policy is None:
            validated[tool] = None
            continue
        if isinstance(policy, (str, bytes)) or not isinstance(
            policy, Sequence
        ):
            raise ValueError(
                "suffix policy must be a sequence of suffixes or None"
            )
        if not policy:
            raise ValueError(
                "suffix policy must not be empty; use None for every file"
            )
        entries: list[str] = []
        for suffix in policy:
            if not isinstance(suffix, str) or not suffix:
                raise ValueError("suffixes must be non-empty strings")
            entries.append(suffix)
        validated[tool] = tuple(entries)
    return validated


def _error_result(tool: StaticAnalysisTool) -> StaticAnalysisResult:
    return StaticAnalysisResult(
        tool=tool,
        status=StaticAnalysisStatus.ERROR,
        error_code=StaticAnalysisErrorCode.UNKNOWN,
    )


def _deadline_for(budget_seconds: float | None) -> float | None:
    """Monotonic deadline for an optional finite positive batch budget."""
    if budget_seconds is None:
        return None
    if isinstance(budget_seconds, bool) or not isinstance(
        budget_seconds, (int, float)
    ):
        raise ValueError("budget_seconds must be a positive number")
    if not math.isfinite(budget_seconds):
        raise ValueError("budget_seconds must be a finite number")
    if budget_seconds <= 0:
        raise ValueError("budget_seconds must be greater than 0")
    return time.monotonic() + float(budget_seconds)