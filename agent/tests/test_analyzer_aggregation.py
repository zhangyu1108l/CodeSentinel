"""Tests for static analysis result aggregation (Phase 8 prep)."""

import pytest

from app.analyzers.aggregation import (
    StaticAnalysisAggregate,
    aggregate_results,
)
from app.analyzers.scheduler import SchedulerOutcome
from app.schemas.review import Category, Severity
from app.schemas.static_analysis import (
    StaticAnalysisErrorCode,
    StaticAnalysisFinding,
    StaticAnalysisResult,
    StaticAnalysisStatus,
    StaticAnalysisTool,
)

TOOLS = StaticAnalysisTool
STATUS = StaticAnalysisStatus
ERRORS = StaticAnalysisErrorCode

NON_OK_STATUSES = [
    (STATUS.UNAVAILABLE, ERRORS.TOOL_NOT_FOUND),
    (STATUS.TIMEOUT, ERRORS.TIMEOUT),
    (STATUS.ERROR, ERRORS.PROCESS_FAILED),
    (STATUS.PARSE_ERROR, ERRORS.INVALID_OUTPUT),
]


def make_finding(tool, rule="R1"):
    return StaticAnalysisFinding(
        tool=tool,
        rule_id=rule,
        category=Category.QUALITY,
        severity=Severity.INFO,
        message="message",
        file_path="src/main.py",
        start_line=1,
        end_line=1,
    )


def ok_result(tool, count=0):
    return StaticAnalysisResult(
        tool=tool,
        status=STATUS.OK,
        findings=[make_finding(tool, f"R{index}") for index in range(count)],
    )


def failed_result(tool, status, error_code):
    return StaticAnalysisResult(
        tool=tool, status=status, error_code=error_code
    )


def outcome(results=(), skipped=(), budget_exhausted=()):
    return SchedulerOutcome(
        results=list(results),
        skipped_tools=list(skipped),
        budget_exhausted_tools=list(budget_exhausted),
    )


class TestAggregate:
    def test_empty_outcome(self):
        aggregate = aggregate_results(SchedulerOutcome())
        assert aggregate.results == []
        assert aggregate.findings == []
        assert aggregate.finding_count == 0
        assert aggregate.completed_tools == []
        assert aggregate.failed_tools == []
        assert aggregate.skipped_tools == []
        assert aggregate.partial is False
        assert aggregate.status_counts == {
            status.value: 0 for status in STATUS
        }

    def test_status_counts_keep_enum_order(self):
        aggregate = aggregate_results(SchedulerOutcome())
        assert list(aggregate.status_counts.keys()) == [
            status.value for status in STATUS
        ]

    def test_ok_results_flatten_findings_in_order(self):
        first = ok_result(TOOLS.RUFF, 2)
        second = ok_result(TOOLS.PMD, 1)
        aggregate = aggregate_results(outcome([first, second]))
        assert aggregate.finding_count == 3
        assert aggregate.findings == [
            first.findings[0],
            first.findings[1],
            second.findings[0],
        ]
        assert aggregate.completed_tools == [TOOLS.RUFF, TOOLS.PMD]
        assert aggregate.failed_tools == []
        assert aggregate.partial is False

    def test_mixed_statuses(self):
        results = [
            ok_result(TOOLS.RUFF, 1),
            failed_result(TOOLS.PMD, *NON_OK_STATUSES[0]),
            failed_result(TOOLS.BANDIT, *NON_OK_STATUSES[1]),
            failed_result(TOOLS.SEMGREP, *NON_OK_STATUSES[2]),
            failed_result(TOOLS.CHECKSTYLE, *NON_OK_STATUSES[3]),
        ]
        aggregate = aggregate_results(outcome(results))
        assert aggregate.status_counts == {
            status.value: 1 for status in STATUS
        }
        assert aggregate.completed_tools == [TOOLS.RUFF]
        assert aggregate.failed_tools == [
            TOOLS.PMD,
            TOOLS.BANDIT,
            TOOLS.SEMGREP,
            TOOLS.CHECKSTYLE,
        ]
        assert aggregate.partial is True
        assert aggregate.finding_count == 1

    @pytest.mark.parametrize("status,error_code", NON_OK_STATUSES)
    def test_each_non_ok_status_marks_the_batch_partial(
        self, status, error_code
    ):
        aggregate = aggregate_results(
            outcome([failed_result(TOOLS.RUFF, status, error_code)])
        )
        assert aggregate.partial is True
        assert aggregate.failed_tools == [TOOLS.RUFF]
        assert aggregate.completed_tools == []
        assert aggregate.status_counts[status.value] == 1

    def test_skipped_tools_are_not_failures(self):
        aggregate = aggregate_results(
            outcome([], skipped=[TOOLS.PMD, TOOLS.CHECKSTYLE])
        )
        assert aggregate.skipped_tools == [
            TOOLS.PMD,
            TOOLS.CHECKSTYLE,
        ]
        assert aggregate.failed_tools == []
        assert aggregate.partial is False

    def test_results_order_is_preserved(self):
        results = [
            ok_result(TOOLS.SEMGREP),
            ok_result(TOOLS.RUFF),
            ok_result(TOOLS.BANDIT),
        ]
        aggregate = aggregate_results(outcome(results))
        assert aggregate.results == results
        assert aggregate.completed_tools == [
            TOOLS.SEMGREP,
            TOOLS.RUFF,
            TOOLS.BANDIT,
        ]

    def test_non_ok_results_contribute_no_findings(self):
        clean = ok_result(TOOLS.RUFF, 1)
        bad = failed_result(
            TOOLS.PMD, STATUS.ERROR, ERRORS.PROCESS_FAILED
        )
        aggregate = aggregate_results(outcome([bad, clean]))
        assert aggregate.finding_count == 1
        assert aggregate.findings == clean.findings

    def test_aggregate_round_trips_through_json(self):
        aggregate = aggregate_results(
            outcome([ok_result(TOOLS.RUFF, 1)], skipped=[TOOLS.PMD])
        )
        dumped = aggregate.model_dump(mode="json")
        assert (
            StaticAnalysisAggregate.model_validate(dumped) == aggregate
        )

    def test_aggregation_is_deterministic(self):
        results = [
            ok_result(TOOLS.RUFF, 2),
            failed_result(TOOLS.PMD, STATUS.TIMEOUT, ERRORS.TIMEOUT),
        ]
        first = aggregate_results(outcome(results))
        second = aggregate_results(outcome(results))
        assert first.model_dump() == second.model_dump()

    @pytest.mark.parametrize(
        "value", [None, [], {"results": []}, "outcome"]
    )
    def test_rejects_non_outcome_input(self, value):
        with pytest.raises(ValueError):
            aggregate_results(value)


class TestBudgetAggregation:
    def test_budget_exhausted_tools_are_reported_and_mark_partial(self):
        aggregate = aggregate_results(
            outcome(
                [ok_result(TOOLS.RUFF, 1)],
                budget_exhausted=[TOOLS.PMD, TOOLS.CHECKSTYLE],
            )
        )
        assert aggregate.budget_exhausted_tools == [
            TOOLS.PMD,
            TOOLS.CHECKSTYLE,
        ]
        assert aggregate.completed_tools == [TOOLS.RUFF]
        assert aggregate.failed_tools == []
        assert aggregate.partial is True
        assert aggregate.finding_count == 1

    def test_budget_exhausted_only_outcome(self):
        aggregate = aggregate_results(
            outcome(budget_exhausted=[TOOLS.SEMGREP])
        )
        assert aggregate.partial is True
        assert aggregate.failed_tools == []
        assert aggregate.completed_tools == []
        assert aggregate.status_counts == {
            status.value: 0 for status in STATUS
        }

    def test_skipped_and_budget_exhausted_are_distinct(self):
        aggregate = aggregate_results(
            outcome(skipped=[TOOLS.PMD], budget_exhausted=[TOOLS.RUFF])
        )
        assert aggregate.skipped_tools == [TOOLS.PMD]
        assert aggregate.budget_exhausted_tools == [TOOLS.RUFF]
        assert aggregate.partial is True

    def test_budget_exhausted_round_trips_through_json(self):
        aggregate = aggregate_results(
            outcome(budget_exhausted=[TOOLS.RUFF])
        )
        dumped = aggregate.model_dump(mode="json")
        assert (
            StaticAnalysisAggregate.model_validate(dumped) == aggregate
        )