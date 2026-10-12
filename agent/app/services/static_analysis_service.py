"""Production static analysis stage (Phase 8.6).

Runs the configured Ruff / Bandit / Semgrep adapters over the changed
files of one review and returns their truthful, aggregated results. The
service only orchestrates: command construction, parsing and status
mapping stay in the Phase 7 adapters, workspace materialization and
target selection stay in the scheduler, and summary computation stays in
the aggregator.

Budget sharing (one review, one RequestBudget):

- every stage shares one absolute monotonic deadline (RequestBudget); no
  stage ever resets it;
- the stage may use at most `stage_share` (default 0.5) of the remaining
  shared budget, so at least the rest stays available for the LLM stage;
- the stage never consumes the derived process cleanup reserve
  (PROCESS_CLEANUP_RESERVE_SECONDS, Phase 8.9): when the remaining time
  is not larger than the reserve, no tool is started and the skip is
  recorded as budget exhausted;
- each tool start is additionally gated by the static scheduler, and the
  executor wrapper (DeadlineCappedExecutor) caps every command at
  execution time to `remaining - reserve`, so a subprocess wait can never
  outlive the shared deadline minus the bounded cleanup.

Truthfulness rules:

- The service never fabricates tool results. A missing executable, a
  timeout, a truncated capture, invalid JSON or a broken process keeps
  its non OK StaticAnalysisResult status and never yields findings.
- A failed tool is never reported as a successful scan with zero
  findings: failed tools appear in failed_tools and degrade the stage.
- Optional capability gaps are reported, not hidden and not treated as
  execution failures (Phase 8.9 decision C): a tool without its trusted
  config or with a blank executable is reported in not_configured_tools
  and does NOT degrade the stage by itself; a tool that was actually
  attempted and failed (UNAVAILABLE / TIMEOUT / ERROR / PARSE_ERROR)
  does.
- No source content, file content, raw stdout/stderr or exception text
  ever leaves this module: only statuses, counts, tool names and finite
  error codes are reported.

The service is synchronous (subprocess IO); callers with an event loop
further up run it in a worker thread.
"""

import logging
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.analyzers.aggregation import (
    StaticAnalysisAggregate,
    aggregate_results,
)
from app.analyzers.bandit_adapter import BanditAdapter
from app.analyzers.execution import (
    DEFAULT_TIMEOUT_SECONDS,
    PROCESS_CLEANUP_RESERVE_SECONDS,
    DeadlineCappedExecutor,
    Executor,
    SubprocessExecutor,
)
from app.analyzers.ruff_adapter import RuffAdapter
from app.analyzers.scheduler import (
    SchedulerOutcome,
    StaticAnalysisScheduler,
)
from app.analyzers.semgrep_adapter import SemgrepAdapter
from app.analyzers.tool_runner import ToolRunner
from app.config.settings import settings
from app.schemas.static_analysis import (
    StaticAnalysisFinding,
    StaticAnalysisResult,
    StaticAnalysisTool,
)
from app.services.request_budget import RequestBudget

logger = logging.getLogger("codesentinel-ai.static_analysis_service")

DEFAULT_STAGE_SHARE = 0.5

REASON_BUDGET_EXHAUSTED = "budget_exhausted"
REASON_NO_FILES = "no_files"
REASON_NO_CONFIGURED_TOOLS = "no_configured_tools"
REASON_DISABLED = "disabled"
NOTE_SEMGREP_CONFIG_INVALID = "semgrep_config_invalid"


@dataclass(frozen=True)
class StaticAnalysisOutcome:
    """Truthful result of one static analysis stage run.

    results holds the per-tool results in execution order (possibly
    empty); aggregate is the deterministic summary of the same results;
    not_configured_tools were skipped before execution (no trusted config)
    and budget_exhausted says whether the stage or the scheduler ran out
    of its share. notes carries short machine readable stage facts, never
    content.
    """

    results: list[StaticAnalysisResult] = field(default_factory=list)
    aggregate: StaticAnalysisAggregate = field(
        default_factory=lambda: aggregate_results(SchedulerOutcome())
    )
    not_configured_tools: list[StaticAnalysisTool] = field(
        default_factory=list
    )
    budget_exhausted: bool = False
    notes: list[str] = field(default_factory=list)
    duration_ms: int = 0

    @property
    def findings(self) -> list[StaticAnalysisFinding]:
        """Flattened findings of the tools that completed successfully."""
        return self.aggregate.findings

    @property
    def degraded(self) -> bool:
        """Whether the stage actually failed or could not complete.

        True as soon as an attempted tool failed (UNAVAILABLE / TIMEOUT /
        ERROR / PARSE_ERROR), the scheduler could not start an applicable
        tool because the stage budget ran out, or the stage itself could
        not run because the shared budget was already spent.

        Optional capability gaps are NOT degradations (Phase 8.9
        decision C): a tool that was never attempted because its trusted
        config or executable is not configured stays in
        not_configured_tools and does not set this flag. A fully
        successful stage is not degraded even when it reports zero
        findings.
        """
        return self.aggregate.partial or self.budget_exhausted

    def report_summary(self) -> dict:
        """Small JSON safe status dict for the review report (no source)."""
        return {
            "tools_run": [result.tool.value for result in self.results],
            "status_counts": dict(self.aggregate.status_counts),
            "findings": self.aggregate.finding_count,
            "completed_tools": [
                tool.value for tool in self.aggregate.completed_tools
            ],
            "failed_tools": [
                tool.value for tool in self.aggregate.failed_tools
            ],
            "skipped_tools": [
                tool.value for tool in self.aggregate.skipped_tools
            ],
            "budget_exhausted_tools": [
                tool.value for tool in self.aggregate.budget_exhausted_tools
            ],
            "not_configured_tools": [
                tool.value for tool in self.not_configured_tools
            ],
            "budget_exhausted": self.budget_exhausted,
            "degraded": self.degraded,
        }


class StaticAnalysisService:
    """Detects, executes and aggregates the configured static tools.

    executables and the Semgrep config come from settings by default and
    may be injected for tests. executor is the Phase 7.2 execution seam:
    tests inject a fake executor so no real process is ever spawned.

    stage_share must be in (0, 1]: it is the fraction of the remaining
    shared budget one static stage may consume.
    """

    def __init__(
        self,
        executor: Executor | None = None,
        ruff_executable: str | None = "ruff",
        bandit_executable: str | None = "bandit",
        semgrep_executable: str | None = "semgrep",
        semgrep_config_path: str | None = None,
        stage_share: float = DEFAULT_STAGE_SHARE,
    ):
        if (
            isinstance(stage_share, bool)
            or not isinstance(stage_share, (int, float))
            or not math.isfinite(stage_share)
            or not 0 < stage_share <= 1
        ):
            raise ValueError("stage_share must be in (0, 1]")
        self._executor = executor
        self._ruff_executable = _normalize_executable(ruff_executable)
        self._bandit_executable = _normalize_executable(bandit_executable)
        self._semgrep_executable = _normalize_executable(semgrep_executable)
        if semgrep_config_path is None:
            semgrep_config_path = (
                settings.STATIC_ANALYSIS_SEMGREP_CONFIG or None
            )
        self._semgrep_config_path = semgrep_config_path or None
        self._stage_share = float(stage_share)

    def analyze(
        self,
        files: Mapping[str, str],
        budget: RequestBudget,
        parent_dir: str | None = None,
    ) -> StaticAnalysisOutcome:
        """Run the configured tools over the given file contents.

        files maps repository relative paths to their text content. Only
        files actually provided are materialized; nothing is read from the
        repository, and every path is validated by the workspace layer
        before anything is written.

        The stage never raises for tool level failures; caller defects
        (bad budget type, invalid mapping) raise ValueError.
        """
        if not isinstance(budget, RequestBudget):
            raise ValueError("budget must be a RequestBudget")
        if not isinstance(files, Mapping):
            raise ValueError("files must be a mapping of path to content")
        started = time.monotonic()
        notes: list[str] = []
        not_configured: list[StaticAnalysisTool] = []

        planned_tools: list[StaticAnalysisTool] = []
        if self._ruff_executable is not None:
            planned_tools.append(StaticAnalysisTool.RUFF)
        else:
            not_configured.append(StaticAnalysisTool.RUFF)
        if self._bandit_executable is not None:
            planned_tools.append(StaticAnalysisTool.BANDIT)
        else:
            not_configured.append(StaticAnalysisTool.BANDIT)
        # Semgrep only joins the plan with a trusted config outside the
        # reviewed workspace; the adapter validates the path again at run
        # time and a blank executable disables the tool explicitly.
        if (
            self._semgrep_executable is not None
            and self._semgrep_config_path is not None
        ):
            planned_tools.append(StaticAnalysisTool.SEMGREP)
        else:
            not_configured.append(StaticAnalysisTool.SEMGREP)

        if not planned_tools:
            return self._empty_outcome(
                not_configured,
                budget_exhausted=False,
                notes=[REASON_NO_CONFIGURED_TOOLS],
                started=started,
            )
        if budget.expired():
            return self._empty_outcome(
                not_configured,
                budget_exhausted=True,
                notes=[REASON_BUDGET_EXHAUSTED],
                started=started,
            )
        if not files:
            return self._empty_outcome(
                not_configured,
                budget_exhausted=False,
                notes=[REASON_NO_FILES],
                started=started,
            )

        remaining = budget.remaining()
        deadline_budget = remaining - PROCESS_CLEANUP_RESERVE_SECONDS
        if deadline_budget <= 0:
            return self._empty_outcome(
                not_configured,
                budget_exhausted=True,
                notes=[REASON_BUDGET_EXHAUSTED],
                started=started,
            )
        stage_budget = min(remaining * self._stage_share, deadline_budget)
        if stage_budget <= 0:
            return self._empty_outcome(
                not_configured,
                budget_exhausted=True,
                notes=[REASON_BUDGET_EXHAUSTED],
                started=started,
            )

        per_tool_timeout = min(
            DEFAULT_TIMEOUT_SECONDS, stage_budget / len(planned_tools)
        )
        base_executor = (
            self._executor
            if self._executor is not None
            else SubprocessExecutor()
        )
        executor = DeadlineCappedExecutor(
            base_executor,
            remaining_seconds=budget.remaining,
            reserve_seconds=PROCESS_CLEANUP_RESERVE_SECONDS,
        )
        runner = ToolRunner(
            executor=executor, timeout_seconds=per_tool_timeout
        )
        adapters: dict[StaticAnalysisTool, object] = {}
        for tool in planned_tools:
            if tool is StaticAnalysisTool.RUFF:
                adapters[tool] = RuffAdapter(runner, self._ruff_executable)
            elif tool is StaticAnalysisTool.BANDIT:
                adapters[tool] = BanditAdapter(
                    runner, self._bandit_executable
                )
        if StaticAnalysisTool.SEMGREP in planned_tools:
            try:
                adapters[StaticAnalysisTool.SEMGREP] = SemgrepAdapter(
                    runner,
                    self._semgrep_config_path,
                    self._semgrep_executable,
                )
            except ValueError:
                # Invalid/missing config path is a configuration problem,
                # never a tool run and never findings. The adapter was
                # never stored, so there is nothing to remove.
                not_configured.append(StaticAnalysisTool.SEMGREP)
                notes.append(NOTE_SEMGREP_CONFIG_INVALID)
                logger.warning(
                    "Semgrep config is invalid; Semgrep is not configured "
                    "for this review"
                )
                if not adapters:
                    notes.append(REASON_NO_CONFIGURED_TOOLS)
                    return self._empty_outcome(
                        not_configured,
                        budget_exhausted=False,
                        notes=notes,
                        started=started,
                    )

        logger.info(
            "Static analysis stage started: tools=%d, not_configured=%d, "
            "stage_budget=%.1fs, per_tool_timeout=%.1fs",
            len(adapters),
            len(not_configured),
            stage_budget,
            per_tool_timeout,
        )

        scheduler = StaticAnalysisScheduler(dict(adapters))
        outcome = scheduler.run_on_contents(
            dict(files),
            parent_dir=parent_dir,
            budget_seconds=stage_budget,
        )
        aggregate = aggregate_results(outcome)
        budget_exhausted = bool(aggregate.budget_exhausted_tools) or (
            budget.expired()
        )
        if budget_exhausted:
            notes.append(REASON_BUDGET_EXHAUSTED)

        result = StaticAnalysisOutcome(
            results=list(aggregate.results),
            aggregate=aggregate,
            not_configured_tools=not_configured,
            budget_exhausted=budget_exhausted,
            notes=notes,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        logger.info(
            "Static analysis stage finished: tools_run=%d, findings=%d, "
            "degraded=%s, budget_exhausted=%s, duration_ms=%d",
            len(result.results),
            result.aggregate.finding_count,
            result.degraded,
            result.budget_exhausted,
            result.duration_ms,
        )
        return result

    def _empty_outcome(
        self,
        not_configured: list[StaticAnalysisTool],
        budget_exhausted: bool,
        notes: list[str],
        started: float,
    ) -> StaticAnalysisOutcome:
        """Outcome for a stage that never started a tool.

        No result is fabricated: with no results the stage cannot claim a
        successful scan, and the reason is recorded explicitly.
        """
        if not not_configured:
            notes = list(notes) + [REASON_NO_CONFIGURED_TOOLS]
        return StaticAnalysisOutcome(
            results=[],
            aggregate=aggregate_results(SchedulerOutcome()),
            not_configured_tools=list(not_configured),
            budget_exhausted=budget_exhausted,
            notes=notes,
            duration_ms=int((time.monotonic() - started) * 1000),
        )


class DisabledStaticAnalysisService:
    """Explicitly disabled static analysis stage (Phase 8.9 decision D).

    Used by the API router when STATIC_ANALYSIS_ENABLED is false: the
    review report carries a stable disabled shape (available=false,
    degraded=false, reason=disabled) instead of omitting the entry, and
    the review is not degraded by a deliberate configuration choice.
    analyze() never starts a tool, never touches the workspace and never
    claims a scan.
    """

    def analyze(
        self,
        files: Mapping[str, str],
        budget: RequestBudget,
        parent_dir: str | None = None,
    ) -> StaticAnalysisOutcome:
        if not isinstance(budget, RequestBudget):
            raise ValueError("budget must be a RequestBudget")
        if not isinstance(files, Mapping):
            raise ValueError("files must be a mapping of path to content")
        return StaticAnalysisOutcome(
            results=[],
            aggregate=aggregate_results(SchedulerOutcome()),
            not_configured_tools=[],
            budget_exhausted=False,
            notes=[REASON_DISABLED],
            duration_ms=0,
        )


def _normalize_executable(value: str | None) -> str | None:
    """Normalize a configured executable name.

    None or a blank value disables the tool explicitly; the tool is then
    reported as not_configured instead of being run with a blank command.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None