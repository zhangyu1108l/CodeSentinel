"""Deterministic finding aggregation (Phase 8.7).

Merges validated agent findings and static analysis findings into one
ordered AnalysisFinding list without inventing data:

- stable fields drive deduplication: file path, line range, category,
  normalized rule id and normalized title;
- cross source merging only uses the fully stable tuple (path, line
  range, category, normalized rule id) and ignores the title, because a
  static tool finding has no title by contract. Different rules, ranges
  or categories are never merged, so distinct issues stay distinct;
- when a static finding merges into an agent finding, the agent entry
  stays primary and gains the STATIC source plus the tool metadata;
- agent-only fields (confidence, title, reason, suggestion) stay None on
  static-only findings instead of being fabricated.

The aggregation is pure and order preserving: agent findings keep their
order first, unmatched static findings follow in tool order.
"""

from pydantic import BaseModel, Field

from app.schemas.report import AnalysisFinding, FindingSource
from app.schemas.review import ReviewFinding
from app.schemas.static_analysis import StaticAnalysisFinding


class AggregationOutcome(BaseModel):
    """Merged findings, the merged duplicate count and source counts."""

    findings: list[AnalysisFinding] = Field(default_factory=list)
    duplicates_merged: int = Field(default=0, ge=0)
    source_counts: dict[str, int] = Field(default_factory=dict)


def aggregate_findings(
    agent_findings: list[ReviewFinding],
    static_findings: list[StaticAnalysisFinding],
) -> AggregationOutcome:
    """Merge both sources deterministically, keeping provenance."""
    merged: list[AnalysisFinding] = []
    stable_index: dict[tuple, int] = {}
    agent_cross_index: dict[tuple, int] = {}
    duplicates = 0

    for finding in agent_findings:
        key = _stable_key(finding.file_path, finding.start_line, finding.end_line, finding.category, finding.rule_id, finding.title)
        if key in stable_index:
            duplicates += 1
            continue
        stable_index[key] = len(merged)
        agent_cross_index[
            _cross_key(finding.file_path, finding.start_line, finding.end_line, finding.category, finding.rule_id)
        ] = len(merged)
        merged.append(_from_agent(finding))

    for finding in static_findings:
        # Static deduplication keeps the producing tool: two tools with
        # the same rule id are evidence from different origins and must
        # not silently lose their metadata.
        key = _static_stable_key(finding)
        if key in stable_index:
            duplicates += 1
            continue
        position = agent_cross_index.get(
            _cross_key(finding.file_path, finding.start_line, finding.end_line, finding.category, finding.rule_id)
        )
        if position is not None:
            existing = merged[position]
            if FindingSource.STATIC not in existing.sources:
                merged[position] = existing.model_copy(
                    update={
                        "sources": existing.sources
                        + [FindingSource.STATIC],
                        "tool": finding.tool,
                    }
                )
            duplicates += 1
            continue
        stable_index[key] = len(merged)
        merged.append(_from_static(finding))

    source_counts = {
        FindingSource.AGENT.value: sum(
            1 for finding in merged
            if finding.sources[0] is FindingSource.AGENT
        ),
        FindingSource.STATIC.value: sum(
            1 for finding in merged
            if finding.sources[0] is FindingSource.STATIC
        ),
    }
    return AggregationOutcome(
        findings=merged,
        duplicates_merged=duplicates,
        source_counts=source_counts,
    )


def _stable_key(
    file_path: str,
    start_line: int,
    end_line: int,
    category,
    rule_id: str,
    title: str | None,
) -> tuple:
    return (
        file_path,
        start_line,
        end_line,
        category,
        _normalize_rule(rule_id),
        _normalize_title(title),
    )


def _static_stable_key(finding: StaticAnalysisFinding) -> tuple:
    return (
        finding.tool,
        finding.file_path,
        finding.start_line,
        finding.end_line,
        finding.category,
        _normalize_rule(finding.rule_id),
    )


def _cross_key(
    file_path: str,
    start_line: int,
    end_line: int,
    category,
    rule_id: str,
) -> tuple:
    return (
        file_path,
        start_line,
        end_line,
        category,
        _normalize_rule(rule_id),
    )


def _normalize_rule(rule_id: str) -> str:
    return rule_id.strip().lower()


def _normalize_title(title: str | None) -> str | None:
    if title is None:
        return None
    normalized = " ".join(title.split()).lower()
    return normalized or None


def _from_agent(finding: ReviewFinding) -> AnalysisFinding:
    return AnalysisFinding(
        sources=[FindingSource.AGENT],
        category=finding.category,
        severity=finding.severity,
        rule_id=finding.rule_id,
        message=finding.description,
        file_path=finding.file_path,
        start_line=finding.start_line,
        end_line=finding.end_line,
        confidence=finding.confidence,
        title=finding.title,
        reason=finding.reason,
        suggestion=finding.suggestion,
        references=list(finding.references),
        agent=finding.category,
    )


def _from_static(finding: StaticAnalysisFinding) -> AnalysisFinding:
    return AnalysisFinding(
        sources=[FindingSource.STATIC],
        category=finding.category,
        severity=finding.severity,
        rule_id=finding.rule_id,
        message=finding.message,
        file_path=finding.file_path,
        start_line=finding.start_line,
        end_line=finding.end_line,
        tool=finding.tool,
    )