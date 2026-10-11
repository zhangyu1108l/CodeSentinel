"""Tests for the shared review budget context and graph routing (8.2)."""

import pytest
from langgraph.graph import END

from app.config.settings import settings
from app.graph.budget import (
    NodeBudgetExhaustedError,
    ReviewBudgetContext,
)
from app.graph.routing import route_next, select_next_node
from app.graph.state import ReviewGraphStatus


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestReviewBudgetContext:
    def test_defaults_to_settings_total_budget(self):
        context = ReviewBudgetContext.create()
        assert context.total_seconds == settings.REVIEW_TOTAL_BUDGET
        assert context.remaining() <= settings.REVIEW_TOTAL_BUDGET

    @pytest.mark.parametrize(
        "seconds", [0, -1, float("nan"), float("inf")]
    )
    def test_invalid_seconds_are_rejected(self, seconds):
        with pytest.raises(ValueError):
            ReviewBudgetContext.create(seconds=seconds)

    def test_node_timeout_is_capped_by_remaining(self):
        clock = FakeClock()
        context = ReviewBudgetContext.create(seconds=10, clock=clock)
        assert context.node_timeout(30) == 10
        clock.advance(6)
        assert context.node_timeout(30) == 4

    def test_llm_timeout_is_capped_by_remaining(self):
        clock = FakeClock()
        context = ReviewBudgetContext.create(seconds=90, clock=clock)
        assert context.llm_timeout(60) == 60
        clock.advance(50)
        assert context.llm_timeout(60) == 40

    def test_expired_after_deadline(self):
        clock = FakeClock()
        context = ReviewBudgetContext.create(seconds=5, clock=clock)
        assert not context.expired()
        clock.advance(5)
        assert context.expired()

    def test_start_node_refuses_when_expired(self):
        clock = FakeClock()
        context = ReviewBudgetContext.create(seconds=1, clock=clock)
        clock.advance(2)
        with pytest.raises(NodeBudgetExhaustedError):
            context.start_node(30)

    def test_two_nodes_share_one_deadline(self):
        clock = FakeClock()
        context = ReviewBudgetContext.create(seconds=10, clock=clock)
        first = context.start_node(30)
        clock.advance(6)
        second = context.start_node(30)
        assert first == 10
        assert second == 4
        # A later node never restarts the full REVIEW_TOTAL_BUDGET.
        assert second < first
        assert context.budget.seconds == 10


class TestGraphRouting:
    def make_state(self, **overrides):
        state = {
            "status": ReviewGraphStatus.PENDING,
            "planned_nodes": ["planner", "bug", "quality"],
            "completed_nodes": [],
        }
        state.update(overrides)
        return state

    def test_selects_first_uncompleted_planned_node(self):
        state = self.make_state(completed_nodes=["planner"])
        assert select_next_node(state) == "bug"

    def test_returns_none_when_all_planned_nodes_completed(self):
        state = self.make_state(
            completed_nodes=["planner", "bug", "quality"]
        )
        assert select_next_node(state) is None

    def test_returns_none_on_budget_exhausted(self):
        state = self.make_state(
            status=ReviewGraphStatus.BUDGET_EXHAUSTED
        )
        assert select_next_node(state) is None

    def test_returns_none_on_unrecoverable_error(self):
        state = self.make_state(
            status=ReviewGraphStatus.UNRECOVERABLE_ERROR
        )
        assert select_next_node(state) is None

    def test_preserves_planned_order(self):
        state = self.make_state(planned_nodes=["quality", "bug"])
        assert select_next_node(state) == "quality"

    def test_route_next_falls_back_to_end(self):
        state = self.make_state(
            status=ReviewGraphStatus.BUDGET_EXHAUSTED
        )
        assert route_next(state) == END

    def test_route_next_returns_next_node(self):
        state = self.make_state()
        assert route_next(state) == "planner"