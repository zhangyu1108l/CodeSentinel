"""Tests for the startup configuration guards."""

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


class TestReviewBudgetAgainstWorkerTimeout:
    def test_defaults_are_valid(self):
        settings = Settings()
        assert settings.REVIEW_TOTAL_BUDGET < settings.AI_SERVICE_TIMEOUT

    @pytest.mark.parametrize("budget", [120, 150, 300])
    def test_budget_equal_to_or_above_worker_timeout_is_rejected(
        self, budget
    ):
        with pytest.raises(ValidationError, match="REVIEW_TOTAL_BUDGET"):
            Settings(REVIEW_TOTAL_BUDGET=budget, AI_SERVICE_TIMEOUT=120)

    @pytest.mark.parametrize(
        "budget", [0, -1, float("nan"), float("inf"), float("-inf")]
    )
    def test_non_finite_or_non_positive_budget_is_rejected(self, budget):
        with pytest.raises(ValidationError, match="REVIEW_TOTAL_BUDGET"):
            Settings(REVIEW_TOTAL_BUDGET=budget, AI_SERVICE_TIMEOUT=120)

    @pytest.mark.parametrize(
        "timeout", [0, -1, float("nan"), float("inf"), float("-inf")]
    )
    def test_non_finite_or_non_positive_worker_timeout_is_rejected(
        self, timeout
    ):
        with pytest.raises(ValidationError, match="AI_SERVICE_TIMEOUT"):
            Settings(REVIEW_TOTAL_BUDGET=100, AI_SERVICE_TIMEOUT=timeout)

    def test_valid_custom_pair_is_accepted(self):
        settings = Settings(REVIEW_TOTAL_BUDGET=60, AI_SERVICE_TIMEOUT=90)
        assert settings.REVIEW_TOTAL_BUDGET == 60
        assert settings.AI_SERVICE_TIMEOUT == 90

    @pytest.mark.parametrize("budget", [110, 109])
    def test_budget_must_keep_the_cleanup_reserve(self, budget):
        # 110 + 11 = 121 >= 120 and 109 + 11 = 120 >= 120 are rejected;
        # 108 + 11 = 119 < 120 is the largest accepted custom budget.
        with pytest.raises(ValidationError, match="cleanup reserve"):
            Settings(REVIEW_TOTAL_BUDGET=budget, AI_SERVICE_TIMEOUT=120)

    def test_budget_just_below_reserve_boundary_is_accepted(self):
        settings = Settings(REVIEW_TOTAL_BUDGET=108, AI_SERVICE_TIMEOUT=120)
        assert settings.REVIEW_TOTAL_BUDGET == 108


class TestValidationErrorsHideInputs:
    """Failure messages stay locatable without echoing the inputs."""

    def test_settings_config_hides_inputs_in_errors(self):
        assert Settings.model_config.get("hide_input_in_errors") is True

    @pytest.mark.parametrize(
        "overrides,reason,fields",
        [
            (
                {"REVIEW_TOTAL_BUDGET": 150, "AI_SERVICE_TIMEOUT": 120},
                "strictly smaller",
                ("REVIEW_TOTAL_BUDGET", "AI_SERVICE_TIMEOUT"),
            ),
            (
                {
                    "REVIEW_TOTAL_BUDGET": float("nan"),
                    "AI_SERVICE_TIMEOUT": 120,
                },
                "REVIEW_TOTAL_BUDGET must be a positive finite number",
                ("REVIEW_TOTAL_BUDGET",),
            ),
            (
                {"REVIEW_TOTAL_BUDGET": 100, "AI_SERVICE_TIMEOUT": 0},
                "AI_SERVICE_TIMEOUT must be a positive finite number",
                ("AI_SERVICE_TIMEOUT",),
            ),
        ],
    )
    def test_reason_is_clear_and_inputs_are_hidden(
        self, overrides, reason, fields
    ):
        kwargs = dict(overrides)
        kwargs["DEEPSEEK_API_KEY"] = "synthetic-sentinel-input"
        with pytest.raises(ValidationError) as exc_info:
            Settings(**kwargs)
        text = str(exc_info.value)
        assert reason in text
        for field in fields:
            assert field in text
        assert "synthetic-sentinel-input" not in text
        assert "input_value" not in text
        assert "input_type" not in text