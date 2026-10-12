"""Tests for the request time budget (Phase 8 timeout governance)."""

import pytest

from app.services.request_budget import (
    RequestBudget,
    ReviewBudgetExceededError,
)


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestRequestBudget:
    @pytest.mark.parametrize(
        "seconds",
        [
            0,
            -1,
            -0.5,
            None,
            "5",
            True,
            float("nan"),
            float("inf"),
            float("-inf"),
        ],
    )
    def test_rejects_invalid_budgets(self, seconds):
        with pytest.raises(ValueError, match="positive finite"):
            RequestBudget(seconds)

    def test_seconds_is_exposed(self):
        budget = RequestBudget(12.5, clock=FakeClock())
        assert budget.seconds == 12.5

    def test_remaining_decreases_with_the_clock(self):
        clock = FakeClock()
        budget = RequestBudget(10, clock=clock)
        assert budget.remaining() == 10
        clock.advance(4)
        assert budget.remaining() == 6

    def test_remaining_never_negative(self):
        clock = FakeClock()
        budget = RequestBudget(5, clock=clock)
        clock.advance(100)
        assert budget.remaining() == 0

    def test_expired_after_the_deadline(self):
        clock = FakeClock()
        budget = RequestBudget(5, clock=clock)
        assert not budget.expired()
        clock.advance(4.999)
        assert not budget.expired()
        clock.advance(0.001)
        assert budget.expired()

    def test_limit_returns_the_smaller_value(self):
        clock = FakeClock()
        budget = RequestBudget(10, clock=clock)
        assert budget.limit(30) == 10
        clock.advance(6)
        assert budget.limit(30) == 4
        assert budget.limit(2) == 2

    def test_limit_is_zero_when_expired(self):
        clock = FakeClock()
        budget = RequestBudget(1, clock=clock)
        clock.advance(2)
        assert budget.limit(30) == 0

    def test_default_clock_counts_down_real_time(self):
        budget = RequestBudget(60)
        assert 0 < budget.remaining() <= 60
        assert not budget.expired()

    def test_budget_exceeded_error_is_an_exception(self):
        with pytest.raises(ReviewBudgetExceededError, match="budget"):
            raise ReviewBudgetExceededError("budget exhausted")