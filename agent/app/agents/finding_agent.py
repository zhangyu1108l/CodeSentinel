"""Dimension specific finding agent (Phase 8.3).

Only categories listed in IMPLEMENTED_AGENT_CATEGORIES may be
instantiated. The planner whitelist is the full Category enum; a planned
agent without an implementation is recorded as skipped by the workflow
instead of being faked. Findings produced by the LLM are validated by the
existing Finding schema and filtered to this agent's category so one
agent cannot report another dimension's findings.
"""

import logging

from app.llm.llm_service import LLMService
from app.prompts.finding_agent import build_finding_agent_messages
from app.schemas.review import Category, ReviewFinding, ReviewTaskRequest

logger = logging.getLogger("codesentinel-ai.finding_agent")

IMPLEMENTED_AGENT_CATEGORIES = frozenset({Category.BUG})


class FindingAgent:
    """One implemented analysis agent for a single review dimension."""

    def __init__(self, category: Category, llm_service: LLMService = None):
        if category not in IMPLEMENTED_AGENT_CATEGORIES:
            raise ValueError(
                "no implementation for agent category: "
                + category.value
            )
        self.category = category
        self.llm_service = llm_service or LLMService()

    async def analyze(
        self, request: ReviewTaskRequest
    ) -> list[ReviewFinding]:
        """Run the dimension analysis and keep only its own findings."""
        messages = build_finding_agent_messages(request, self.category)
        findings = await self.llm_service.generate_findings(messages)
        kept = [
            finding
            for finding in findings
            if finding.category == self.category
        ]
        dropped = len(findings) - len(kept)
        if dropped:
            logger.warning(
                "Dropped %d finding(s) outside the %s category",
                dropped,
                self.category.value,
            )
        logger.info(
            "Finding agent %s produced %d finding(s)",
            self.category.value,
            len(kept),
        )
        return kept