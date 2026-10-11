"""Minimal planner agent (Phase 8.3).

Turns one review request into an AnalysisPlan that is constrained by the
code-defined agent whitelist (Category) through schema validation. The
planner cannot emit executable code, tool names or arbitrary fields.
"""

from app.llm.llm_service import LLMService
from app.prompts.planner import build_planner_messages
from app.schemas.plan import AnalysisPlan
from app.schemas.review import ReviewTaskRequest


class PlannerAgent:
    """Plans the review dimensions for one pull request."""

    def __init__(self, llm_service: LLMService = None):
        self.llm_service = llm_service or LLMService()

    async def plan(self, request: ReviewTaskRequest) -> AnalysisPlan:
        """Return the whitelist constrained plan for one request."""
        messages = build_planner_messages(request)
        return await self.llm_service.generate_structured(
            messages, AnalysisPlan
        )