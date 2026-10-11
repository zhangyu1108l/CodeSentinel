"""Dimension specific finding agent (Phase 8.3/8.4).

Only categories listed in IMPLEMENTED_AGENT_CATEGORIES may be
instantiated. The planner whitelist is the full Category enum; a planned
agent without an implementation is recorded as skipped by the workflow
instead of being faked.

Phase 8.4 adds the verified context loop: the agent runs only when a
usable AgentContextPayload exists (no context means no LLM call and an
empty finding list, never fabricated findings), and every LLM finding is
verified against the payload before it is returned:

- category must equal this agent's category;
- file_path must be one of the payload paths;
- start_line/end_line must both lie inside one allowed range;
- title/rule_id/description/reason/suggestion must not be blank;
- identical findings (path, lines, rule, case-insensitive title) are
  deduplicated, keeping the first occurrence.

The long prompt payload embeds untrusted source and is never logged; only
counts are logged.
"""

import logging

from app.agents.context_payload import AgentContextPayload
from app.llm.llm_service import LLMService
from app.prompts.finding_agent import build_finding_agent_messages
from app.schemas.review import Category, ReviewFinding, ReviewTaskRequest

logger = logging.getLogger("codesentinel-ai.finding_agent")

IMPLEMENTED_AGENT_CATEGORIES = frozenset({Category.BUG})

_EVIDENCE_FIELDS = (
    "title",
    "rule_id",
    "description",
    "reason",
    "suggestion",
)


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
        self,
        request: ReviewTaskRequest,
        context: AgentContextPayload | None = None,
    ) -> list[ReviewFinding]:
        """Analyse one request on a verified context; [] without context."""
        if context is None or not context.available:
            logger.info(
                "Finding agent %s skipped: no usable code context",
                self.category.value,
            )
            return []

        messages = build_finding_agent_messages(
            request, self.category, context=context
        )
        findings = await self.llm_service.generate_findings(messages)
        kept = normalize_findings(findings, context, self.category)
        dropped = len(findings) - len(kept)
        if dropped:
            logger.warning(
                "Dropped %d finding(s) failing verification (%s)",
                dropped,
                self.category.value,
            )
        logger.info(
            "Finding agent %s produced %d verified finding(s)",
            self.category.value,
            len(kept),
        )
        return kept


def normalize_findings(
    findings: list[ReviewFinding],
    context: AgentContextPayload,
    category: Category,
) -> list[ReviewFinding]:
    """Keep only verified, non duplicated findings in input order."""
    kept: list[ReviewFinding] = []
    seen: set[tuple] = set()
    for finding in findings:
        if not _is_verified(finding, context, category):
            continue
        key = _dedup_key(finding)
        if key in seen:
            continue
        seen.add(key)
        kept.append(finding)
    return kept


def _is_verified(
    finding: ReviewFinding,
    context: AgentContextPayload,
    category: Category,
) -> bool:
    if finding.category != category:
        return False
    ranges = context.line_ranges.get(finding.file_path)
    if not ranges:
        return False
    if finding.start_line < 1 or finding.end_line < finding.start_line:
        return False
    if not any(
        start <= finding.start_line and finding.end_line <= end
        for start, end in ranges
    ):
        return False
    return all(
        getattr(finding, field).strip() for field in _EVIDENCE_FIELDS
    )


def _dedup_key(finding: ReviewFinding) -> tuple:
    return (
        finding.file_path,
        finding.start_line,
        finding.end_line,
        finding.rule_id,
        finding.title.strip().lower(),
    )