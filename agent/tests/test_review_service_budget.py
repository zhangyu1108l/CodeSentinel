"""Tests for the request budget integration in ReviewService."""

import asyncio
import time

import pytest

from app.config.settings import settings
from app.schemas.review import (
    Category,
    ReviewFinding,
    ReviewTaskRequest,
    Severity,
)
from app.services.request_budget import ReviewBudgetExceededError
from app.services.review_service import (
    ReviewService,
    _positive_seconds,
)

VALID_FINDING = ReviewFinding(
    category=Category.QUALITY,
    severity=Severity.LOW,
    confidence=0.5,
    rule_id="MOCK-001",
    title="Finding title",
    file_path="src/Main.java",
    start_line=1,
    end_line=1,
    description="description",
    reason="reason",
    suggestion="suggestion",
    references=["MOCK"],
)


def make_request(**overrides):
    data = {
        "task_id": 7,
        "repository": "owner/repo",
        "pr_number": 42,
        "commit_sha": "abc123",
        "files": [],
    }
    data.update(overrides)
    return ReviewTaskRequest(**data)


class ImmediateLLM:
    def __init__(self, findings=None):
        self.findings = list(findings or [])
        self.calls = 0

    async def generate_findings(self, messages):
        self.calls += 1
        return self.findings


class SlowLLM:
    def __init__(self, seconds):
        self.seconds = seconds
        self.calls = 0
        self.cancelled = False

    async def generate_findings(self, messages):
        self.calls += 1
        try:
            await asyncio.sleep(self.seconds)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return []


class InnerTimeoutLLM:
    async def generate_findings(self, messages):
        raise TimeoutError("inner timeout")


class RaisingLLM:
    async def generate_findings(self, messages):
        raise RuntimeError("llm down")


class FailingContext:
    def __init__(self, error):
        self.error = error
        self.calls = 0

    async def fetch(self, task_id):
        self.calls += 1
        raise self.error


class SlowContext:
    def __init__(self, seconds):
        self.seconds = seconds
        self.calls = 0
        self.cancelled = False

    async def fetch(self, task_id):
        self.calls += 1
        try:
            await asyncio.sleep(self.seconds)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return None


class TestReviewBudget:
    def test_invalid_budgets_are_rejected(self):
        for value in (
            0,
            -1,
            "5",
            float("nan"),
            float("inf"),
            float("-inf"),
        ):
            with pytest.raises(ValueError, match="positive finite"):
                ReviewService(request_budget_seconds=value)
            with pytest.raises(ValueError, match="positive finite"):
                ReviewService(context_timeout_seconds=value)

    def test_default_budget_derivation_holds(self):
        assert (
            settings.REVIEW_TOTAL_BUDGET
            >= settings.PR_CONTEXT_TIMEOUT + settings.DEEPSEEK_TIMEOUT
        )
        assert settings.REVIEW_TOTAL_BUDGET < settings.AI_SERVICE_TIMEOUT

    def test_completed_review_under_budget(self):
        llm = ImmediateLLM([VALID_FINDING])
        service = ReviewService(
            llm_service=llm, request_budget_seconds=5
        )
        result = asyncio.run(service.review(make_request()))
        assert result.status == "COMPLETED"
        assert result.findings == [VALID_FINDING]
        assert llm.calls == 1

    def test_llm_is_cancelled_when_budget_expires(self):
        llm = SlowLLM(5)
        service = ReviewService(
            llm_service=llm, request_budget_seconds=0.05
        )
        started = time.monotonic()
        with pytest.raises(ReviewBudgetExceededError, match="budget"):
            asyncio.run(service.review(make_request()))
        assert llm.calls == 1
        assert llm.cancelled is True
        assert time.monotonic() - started < 2

    def test_llm_not_called_when_budget_already_exhausted(self):
        llm = ImmediateLLM([VALID_FINDING])
        service = ReviewService(
            llm_service=llm, request_budget_seconds=1e-9
        )
        with pytest.raises(ReviewBudgetExceededError):
            asyncio.run(service.review(make_request()))
        assert llm.calls == 0

    def test_slow_context_is_cancelled_and_budget_fails_review(self):
        context = SlowContext(5)
        llm = ImmediateLLM([VALID_FINDING])
        service = ReviewService(
            llm_service=llm,
            pr_context_client=context,
            request_budget_seconds=0.05,
        )
        started = time.monotonic()
        with pytest.raises(ReviewBudgetExceededError):
            asyncio.run(service.review(make_request()))
        assert context.calls == 1
        assert context.cancelled is True
        assert llm.calls == 0
        assert time.monotonic() - started < 2

    def test_context_timeout_degrades_and_llm_still_runs(self):
        context = SlowContext(5)
        llm = ImmediateLLM([VALID_FINDING])
        service = ReviewService(
            llm_service=llm,
            pr_context_client=context,
            request_budget_seconds=5,
            context_timeout_seconds=0.05,
        )
        result = asyncio.run(service.review(make_request()))
        assert result.status == "DEGRADED"
        assert result.findings == [VALID_FINDING]
        assert result.report["context"]["reason"] == "TimeoutError"
        assert llm.calls == 1

    def test_degraded_result_keeps_existing_report_shape(self):
        context = FailingContext(RuntimeError("context down"))
        service = ReviewService(
            llm_service=ImmediateLLM(),
            pr_context_client=context,
            request_budget_seconds=5,
        )
        result = asyncio.run(service.review(make_request()))
        assert result.status == "DEGRADED"
        assert set(result.report) == {
            "summary",
            "total_findings",
            "context",
        }
        assert result.report["context"]["degraded"] is True

    def test_llm_failure_is_not_disguised_as_success(self):
        service = ReviewService(
            llm_service=RaisingLLM(), request_budget_seconds=5
        )
        with pytest.raises(RuntimeError, match="llm down"):
            asyncio.run(service.review(make_request()))

    def test_inner_timeout_is_not_mislabeled_when_budget_remains(self):
        service = ReviewService(
            llm_service=InnerTimeoutLLM(), request_budget_seconds=5
        )
        with pytest.raises(TimeoutError) as exc_info:
            asyncio.run(service.review(make_request()))
        assert not isinstance(
            exc_info.value, ReviewBudgetExceededError
        )


class TestPositiveSeconds:
    @pytest.mark.parametrize(
        "value",
        [
            0,
            -1,
            -0.5,
            float("nan"),
            float("inf"),
            float("-inf"),
            "5",
            True,
        ],
    )
    def test_rejects_invalid_values(self, value):
        with pytest.raises(ValueError, match="finite"):
            _positive_seconds(value, "timeout")

    def test_accepts_a_finite_positive_value(self):
        assert _positive_seconds(2.5, "timeout") == 2.5