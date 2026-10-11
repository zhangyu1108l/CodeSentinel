"""Tests for the planner schema and PlannerAgent (Phase 8.3)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.agents.planner import PlannerAgent
from app.llm.exceptions import LLMResponseError
from app.llm.llm_service import LLMService
from app.schemas.plan import AnalysisPlan, AnalysisTask
from app.schemas.review import Category, ReviewTaskRequest


def make_request():
    return ReviewTaskRequest(
        task_id=1,
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        files=["a.py"],
    )


class TestAnalysisPlanSchema:
    def test_valid_plan_parses(self):
        plan = AnalysisPlan.model_validate(
            {"tasks": [{"agent": "BUG"}, {"agent": "SECURITY"}]}
        )
        assert plan.agents == [Category.BUG, Category.SECURITY]

    def test_unknown_agent_is_rejected(self):
        with pytest.raises(ValidationError):
            AnalysisPlan.model_validate(
                {"tasks": [{"agent": "HACKER"}]}
            )

    def test_empty_plan_is_rejected(self):
        with pytest.raises(ValidationError):
            AnalysisPlan.model_validate({"tasks": []})

    def test_duplicate_agent_is_rejected(self):
        with pytest.raises(ValidationError):
            AnalysisPlan.model_validate(
                {"tasks": [{"agent": "BUG"}, {"agent": "BUG"}]}
            )

    def test_extra_fields_are_rejected(self):
        with pytest.raises(ValidationError):
            AnalysisPlan.model_validate(
                {"tasks": [{"agent": "BUG", "command": "rm -rf /"}]}
            )
        with pytest.raises(ValidationError):
            AnalysisPlan.model_validate(
                {"tasks": [{"agent": "BUG"}], "tools": ["curl"]}
            )

    def test_task_has_no_executable_fields(self):
        assert set(AnalysisTask.model_fields) == {"agent"}


class TestPlannerAgent:
    def make_planner(self, plan):
        llm = MagicMock(spec=LLMService)
        llm.generate_structured = AsyncMock(return_value=plan)
        return PlannerAgent(llm_service=llm), llm

    def make_plan(self):
        return AnalysisPlan.model_validate({"tasks": [{"agent": "BUG"}]})

    def test_returns_plan_from_llm_service(self):
        plan = self.make_plan()
        planner, llm = self.make_planner(plan)

        result = asyncio.run(planner.plan(make_request()))

        assert result is plan
        llm.generate_structured.assert_called_once()

    def test_messages_are_whitelist_constrained(self):
        planner, llm = self.make_planner(self.make_plan())

        asyncio.run(planner.plan(make_request()))

        messages, schema = llm.generate_structured.call_args[0]
        assert schema is AnalysisPlan
        assert messages[0]["role"] == "system"
        for value in ("BUG", "SECURITY", "PERFORMANCE", "QUALITY"):
            assert value in messages[0]["content"]
        assert "whitelist" in messages[0]["content"].lower()
        assert "a.py" in messages[1]["content"]

    def test_single_llm_call_per_plan(self):
        planner, llm = self.make_planner(self.make_plan())

        asyncio.run(planner.plan(make_request()))

        assert llm.generate_structured.await_count == 1

    def test_llm_failure_propagates(self):
        llm = MagicMock(spec=LLMService)
        llm.generate_structured = AsyncMock(
            side_effect=LLMResponseError("bad plan")
        )
        planner = PlannerAgent(llm_service=llm)

        with pytest.raises(LLMResponseError):
            asyncio.run(planner.plan(make_request()))