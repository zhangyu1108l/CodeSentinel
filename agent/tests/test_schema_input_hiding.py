"""Defense-in-depth tests: boundary DTOs hide validation input previews."""

import pytest
from pydantic import ValidationError

from app.schemas.llm_output import LlmReviewOutput
from app.schemas.pr_context import PrContext
from app.schemas.review import ReviewTaskResult

SENTINEL = "SENTINEL-DTO-INPUT-DO-NOT-SHOW"


def invalid_pr_context():
    return {
        "taskId": 1,
        "owner": "owner",
        "repo": "repo",
        "prNumber": 1,
        "commitSha": "sha",
        "files": [{"status": "modified", "content": SENTINEL}],
    }


def invalid_llm_output():
    return {"findings": [{"category": "BUG", "description": SENTINEL}]}


def invalid_review_result():
    return {
        "task_id": 1,
        "status": "COMPLETED",
        "report": {},
        "findings": [
            {
                "category": "BUG",
                "severity": "HIGH",
                "confidence": 0.5,
                "rule_id": "R1",
                "title": "title",
                "file_path": "a.py",
                "start_line": 1,
                "end_line": 1,
                "description": SENTINEL,
                "reason": "reason",
                "references": [],
            }
        ],
    }


CASES = [
    (PrContext, invalid_pr_context),
    (LlmReviewOutput, invalid_llm_output),
    (ReviewTaskResult, invalid_review_result),
]


class TestBoundaryModelsHideInput:
    @pytest.mark.parametrize("model,payload_factory", CASES)
    def test_hide_input_flag_is_enabled(self, model, payload_factory):
        assert model.model_config.get("hide_input_in_errors") is True

    @pytest.mark.parametrize("model,payload_factory", CASES)
    def test_validation_error_string_hides_input(
        self, model, payload_factory
    ):
        with pytest.raises(ValidationError) as exc_info:
            model.model_validate(payload_factory())

        text = str(exc_info.value)
        assert SENTINEL not in text
        assert "input_value" not in text
        assert len(exc_info.value.errors(include_input=False)) >= 1