"""Tests for the dimension specific finding agent (Phase 8.3/8.4)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.context_payload import AgentContextPayload
from app.agents.finding_agent import (
    IMPLEMENTED_AGENT_CATEGORIES,
    FindingAgent,
    normalize_findings,
)
from app.llm.exceptions import LLMException
from app.llm.llm_service import LLMService
from app.schemas.review import (
    Category,
    ReviewFinding,
    ReviewTaskRequest,
    Severity,
)


def make_finding(
    category=Category.BUG,
    start=5,
    end=6,
    title="title",
    description="description",
    file_path="a.py",
):
    return ReviewFinding(
        category=category,
        severity=Severity.HIGH,
        confidence=0.5,
        rule_id="R1",
        title=title,
        file_path=file_path,
        start_line=start,
        end_line=end,
        description=description,
        reason="reason",
        suggestion="suggestion",
        references=[],
    )


def make_request():
    return ReviewTaskRequest(
        task_id=1,
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        files=[],
    )


def make_payload(
    available=True,
    code_section="CODE-SENTINEL",
    static_section="",
    paths=None,
    line_ranges=None,
):
    return AgentContextPayload(
        available=available,
        reason=None if available else "context_unavailable",
        repository="owner/repo",
        pr_number=2,
        commit_sha="abc123",
        code_section=code_section,
        static_section=static_section,
        paths=paths if paths is not None else ["a.py"],
        line_ranges=(
            line_ranges if line_ranges is not None else {"a.py": [(1, 10)]}
        ),
    )


def make_agent(findings=None, error=None):
    llm = MagicMock(spec=LLMService)
    if error is not None:
        llm.generate_findings = AsyncMock(side_effect=error)
    else:
        llm.generate_findings = AsyncMock(return_value=findings or [])
    return FindingAgent(Category.BUG, llm_service=llm), llm


class TestFindingAgent:
    def test_all_planner_categories_are_implemented(self):
        assert IMPLEMENTED_AGENT_CATEGORIES == frozenset(Category)

    def test_every_dimension_can_be_instantiated(self):
        for category in Category:
            agent = FindingAgent(category)
            assert agent.category is category

    def test_without_context_skips_llm_and_returns_empty(self):
        agent, llm = make_agent(findings=[make_finding()])

        assert asyncio.run(agent.analyze(make_request())) == []

        llm.generate_findings.assert_not_called()

    def test_unavailable_payload_skips_llm(self):
        agent, llm = make_agent(findings=[make_finding()])

        result = asyncio.run(
            agent.analyze(make_request(), make_payload(available=False))
        )

        assert result == []
        llm.generate_findings.assert_not_called()

    def test_verified_finding_is_kept(self):
        finding = make_finding()
        agent, llm = make_agent(findings=[finding])

        result = asyncio.run(agent.analyze(make_request(), make_payload()))

        assert result == [finding]
        assert llm.generate_findings.await_count == 1

    def test_prompt_carries_context_static_and_allowed_ranges(self):
        agent, llm = make_agent(findings=[])

        asyncio.run(
            agent.analyze(
                make_request(),
                make_payload(
                    code_section="CODE-SENTINEL",
                    static_section="STATIC-SENTINEL",
                ),
            )
        )

        messages = llm.generate_findings.call_args[0][0]
        user = messages[1]["content"]
        assert "CODE-SENTINEL" in user
        assert "STATIC-SENTINEL" in user
        assert "a.py: 1-10" in user
        assert '"findings"' in messages[0]["content"]
        assert "BUG" in messages[0]["content"]

    def test_other_category_is_dropped(self):
        agent, _ = make_agent(
            findings=[make_finding(category=Category.SECURITY)]
        )

        assert (
            asyncio.run(agent.analyze(make_request(), make_payload())) == []
        )

    def test_out_of_path_is_dropped(self):
        agent, _ = make_agent(
            findings=[make_finding(file_path="b.py")]
        )

        assert (
            asyncio.run(agent.analyze(make_request(), make_payload())) == []
        )

    def test_out_of_range_is_dropped(self):
        agent, _ = make_agent(findings=[make_finding(start=20, end=22)])

        assert (
            asyncio.run(agent.analyze(make_request(), make_payload())) == []
        )

    def test_inverted_range_is_dropped(self):
        agent, _ = make_agent(findings=[make_finding(start=8, end=3)])

        assert (
            asyncio.run(agent.analyze(make_request(), make_payload())) == []
        )

    def test_blank_evidence_is_dropped(self):
        agent, _ = make_agent(
            findings=[make_finding(description="   ")]
        )

        assert (
            asyncio.run(agent.analyze(make_request(), make_payload())) == []
        )

    def test_duplicates_are_collapsed(self):
        first = make_finding(title="Duplicate")
        second = make_finding(title="duplicate")
        agent, _ = make_agent(findings=[first, second])

        result = asyncio.run(agent.analyze(make_request(), make_payload()))

        assert result == [first]

    def test_normalize_keeps_order_and_drops_duplicates(self):
        findings = [
            make_finding(start=1, end=2, title="A"),
            make_finding(start=1, end=2, title="a"),
            make_finding(file_path="b.py"),
        ]

        kept = normalize_findings(findings, make_payload(), Category.BUG)

        assert kept == [findings[0]]

    def test_empty_llm_result_is_legal(self):
        agent, _ = make_agent(findings=[])

        result = asyncio.run(agent.analyze(make_request(), make_payload()))

        assert result == []

    def test_llm_failure_propagates(self):
        agent, _ = make_agent(error=LLMException("down"))

        with pytest.raises(LLMException):
            asyncio.run(agent.analyze(make_request(), make_payload()))