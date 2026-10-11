"""Per dimension tests for the Phase 8.7 finding agents.

Fake LLM only: no real model call. Every dimension uses the same agent
implementation, its own prompt guidance and the same verification rules.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.context_payload import AgentContextPayload
from app.agents.finding_agent import (
    IMPLEMENTED_AGENT_CATEGORIES,
    FindingAgent,
)
from app.llm.llm_service import LLMService
from app.schemas.review import (
    Category,
    ReviewFinding,
    ReviewTaskRequest,
    Severity,
)

GUIDANCE_MARKERS = {
    Category.BUG: "boundary",
    Category.SECURITY: "injection",
    Category.PERFORMANCE: "N+1",
    Category.QUALITY: "duplication",
}


def make_request():
    return ReviewTaskRequest(
        task_id=1,
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        files=[],
    )


def make_payload(available=True):
    return AgentContextPayload(
        available=available,
        reason=None if available else "context_unavailable",
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        code_section="CODE",
        paths=["a.py"],
        line_ranges={"a.py": [(1, 10)]},
    )


def make_finding(category):
    return ReviewFinding(
        category=category,
        severity=Severity.HIGH,
        confidence=0.5,
        rule_id=f"{category.value}-R1",
        title=f"{category.value} finding",
        file_path="a.py",
        start_line=1,
        end_line=1,
        description="description",
        reason="reason",
        suggestion="suggestion",
        references=[],
    )


def make_agent(category, findings=None, error=None):
    llm = MagicMock(spec=LLMService)
    if error is not None:
        llm.generate_findings = AsyncMock(side_effect=error)
    else:
        llm.generate_findings = AsyncMock(return_value=findings or [])
    return FindingAgent(category, llm_service=llm), llm


class TestImplementedDimensions:
    def test_all_four_dimensions_are_implemented(self):
        assert IMPLEMENTED_AGENT_CATEGORIES == {
            Category.BUG,
            Category.SECURITY,
            Category.PERFORMANCE,
            Category.QUALITY,
        }

    @pytest.mark.parametrize("category", list(Category))
    def test_prompt_carries_dimension_guidance(self, category):
        agent, llm = make_agent(category)

        asyncio.run(agent.analyze(make_request(), make_payload()))

        system = llm.generate_findings.call_args[0][0][0]["content"]
        assert category.value in system
        assert GUIDANCE_MARKERS[category].lower() in system.lower()

    @pytest.mark.parametrize("category", list(Category))
    def test_own_category_finding_is_kept(self, category):
        finding = make_finding(category)
        agent, _ = make_agent(category, findings=[finding])

        result = asyncio.run(agent.analyze(make_request(), make_payload()))

        assert result == [finding]

    @pytest.mark.parametrize("category", list(Category))
    def test_other_category_finding_is_dropped(self, category):
        other = next(
            value for value in Category if value is not category
        )
        agent, _ = make_agent(category, findings=[make_finding(other)])

        result = asyncio.run(agent.analyze(make_request(), make_payload()))

        assert result == []

    @pytest.mark.parametrize("category", list(Category))
    def test_without_context_no_llm_call_and_no_findings(self, category):
        agent, llm = make_agent(category, findings=[make_finding(category)])

        assert asyncio.run(agent.analyze(make_request())) == []
        assert (
            asyncio.run(
                agent.analyze(make_request(), make_payload(False))
            )
            == []
        )

        llm.generate_findings.assert_not_called()

    @pytest.mark.parametrize("category", list(Category))
    def test_llm_failure_propagates_per_dimension(self, category):
        from app.llm.exceptions import LLMResponseError

        agent, _ = make_agent(
            category, error=LLMResponseError("down")
        )

        with pytest.raises(LLMResponseError):
            asyncio.run(agent.analyze(make_request(), make_payload()))