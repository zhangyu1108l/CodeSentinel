"""Unified finding validator (Phase 8.7).

The validator is the single gate between produced findings and the
reported result. It validates, against the bounded agent context payload:

- agent (LLM) findings: allowed file path, line range inside one allowed
  range, non-blank evidence fields, schema level category / severity /
  confidence (enforced by ReviewFinding), deterministic deduplication;
- static analysis findings: only hard invariants (relative path, line
  sanity, non-blank rule / message). Static findings are never dropped
  for missing LLM style fields (title, description, confidence).

Because the payload may be truncated, a static finding whose location is
not covered by the payload is kept and counted as unverified instead of
being dropped: deterministic tool output stays valid evidence, and
deleting it because the bounded payload dropped a file tail would lose
real issues.

Every drop reason is counted in a small, content free summary; source
lines, model output and exception messages are never recorded.
"""

import logging

from pydantic import BaseModel, Field

from app.agents.context_payload import AgentContextPayload
from app.agents.finding_agent import EVIDENCE_FIELDS
from app.schemas.review import ReviewFinding
from app.schemas.static_analysis import (
    StaticAnalysisFinding,
    is_repo_relative_path,
)

logger = logging.getLogger("codesentinel-ai.validator")

REASON_NO_CONTEXT = "no_context"
REASON_CATEGORY_NOT_PLANNED = "category_not_planned"
REASON_PATH_NOT_ALLOWED = "path_not_allowed"
REASON_LINE_RANGE = "line_range_out_of_bounds"
REASON_BLANK_EVIDENCE = "blank_evidence"
REASON_DUPLICATE = "duplicate"
REASON_INVALID_STATIC = "invalid_static"

UNVERIFIED_NOT_IN_PAYLOAD = "not_in_payload"
UNVERIFIED_NO_PAYLOAD = "payload_unavailable"


class ValidationOutcome(BaseModel):
    """Kept findings plus the deterministic drop reason counts.

    changed_line_* / not_on_changed_lines / anchor_unknown classify the
    kept findings against the diff changed lines when that information is
    available; they are measurements, not filters: a finding off the
    changed lines is still a valid finding, it is only not anchored to
    the diff. anchor_unknown means no changed-line information existed
    for the file.
    """

    findings: list[ReviewFinding] = Field(default_factory=list)
    static_findings: list[StaticAnalysisFinding] = Field(
        default_factory=list
    )
    agent_checked: int = Field(default=0, ge=0)
    static_checked: int = Field(default=0, ge=0)
    dropped_findings: dict[str, int] = Field(default_factory=dict)
    dropped_static: dict[str, int] = Field(default_factory=dict)
    static_unverified: int = Field(default=0, ge=0)
    unverified_reasons: dict[str, int] = Field(default_factory=dict)
    changed_line_anchored: int = Field(default=0, ge=0)
    not_on_changed_lines: int = Field(default=0, ge=0)
    anchor_unknown: int = Field(default=0, ge=0)
    static_changed_line_anchored: int = Field(default=0, ge=0)
    static_not_on_changed_lines: int = Field(default=0, ge=0)
    static_anchor_unknown: int = Field(default=0, ge=0)

    def summary(self) -> dict:
        """Small, log safe validation summary (counts and reason codes)."""
        return {
            "agent_checked": self.agent_checked,
            "agent_kept": len(self.findings),
            "agent_dropped": dict(self.dropped_findings),
            "static_checked": self.static_checked,
            "static_kept": len(self.static_findings),
            "static_dropped": dict(self.dropped_static),
            "static_unverified": self.static_unverified,
            "unverified_reasons": dict(self.unverified_reasons),
            "changed_line_anchored": self.changed_line_anchored,
            "not_on_changed_lines": self.not_on_changed_lines,
            "anchor_unknown": self.anchor_unknown,
            "static_changed_line_anchored": (
                self.static_changed_line_anchored
            ),
            "static_not_on_changed_lines": (
                self.static_not_on_changed_lines
            ),
            "static_anchor_unknown": self.static_anchor_unknown,
        }


class Validator:
    """Validates agent and static findings against the context payload."""

    def validate(
        self,
        payload: AgentContextPayload | None,
        agent_findings: list[ReviewFinding],
        static_findings: list[StaticAnalysisFinding],
        allowed_categories=None,
        changed_ranges=None,
    ) -> ValidationOutcome:
        """Return the kept findings and the drop reason counts.

        allowed_categories optionally restricts findings to the categories
        of the agents that actually ran in this pipeline. changed_ranges
        optionally classifies kept findings against the diff changed lines
        (path -> list of inclusive ranges); classification is reported,
        never used to drop findings. Confidence and severity are never
        rewritten: the validator does not promote model output.
        """
        findings, dropped = _validate_agent_findings(
            payload, agent_findings, allowed_categories
        )
        statics, dropped_static, unverified, unverified_reasons = (
            _validate_static_findings(payload, static_findings)
        )
        anchored, not_on_changed, unknown = _anchor_counts(
            [
                (
                    finding.file_path,
                    finding.start_line,
                    finding.end_line,
                )
                for finding in findings
            ],
            changed_ranges,
        )
        (
            static_anchored,
            static_not_on_changed,
            static_unknown,
        ) = _anchor_counts(
            [
                (
                    finding.file_path,
                    finding.start_line,
                    finding.end_line,
                )
                for finding in statics
            ],
            changed_ranges,
        )
        outcome = ValidationOutcome(
            findings=findings,
            static_findings=statics,
            agent_checked=len(agent_findings),
            static_checked=len(static_findings),
            dropped_findings=dropped,
            dropped_static=dropped_static,
            static_unverified=unverified,
            unverified_reasons=unverified_reasons,
            changed_line_anchored=anchored,
            not_on_changed_lines=not_on_changed,
            anchor_unknown=unknown,
            static_changed_line_anchored=static_anchored,
            static_not_on_changed_lines=static_not_on_changed,
            static_anchor_unknown=static_unknown,
        )
        logger.info(
            "Validation finished: agent kept=%d dropped=%d, static kept=%d "
            "dropped=%d unverified=%d",
            len(findings),
            len(agent_findings) - len(findings),
            len(statics),
            len(static_findings) - len(statics),
            unverified,
        )
        return outcome


def _validate_agent_findings(
    payload: AgentContextPayload | None,
    findings: list[ReviewFinding],
    allowed_categories=None,
) -> tuple[list[ReviewFinding], dict[str, int]]:
    dropped: dict[str, int] = {}
    if payload is None or not payload.available:
        if findings:
            dropped[REASON_NO_CONTEXT] = len(findings)
        return [], dropped

    kept: list[ReviewFinding] = []
    seen: set[tuple] = set()
    for finding in findings:
        reason = _agent_drop_reason(
            finding, payload, seen, allowed_categories
        )
        if reason is not None:
            dropped[reason] = dropped.get(reason, 0) + 1
            continue
        seen.add(_agent_dedup_key(finding))
        kept.append(finding)
    return kept, dropped


def _agent_drop_reason(
    finding: ReviewFinding,
    payload: AgentContextPayload,
    seen: set[tuple],
    allowed_categories=None,
) -> str | None:
    if (
        allowed_categories is not None
        and finding.category not in allowed_categories
    ):
        return REASON_CATEGORY_NOT_PLANNED
    if not all(
        getattr(finding, field).strip() for field in EVIDENCE_FIELDS
    ):
        return REASON_BLANK_EVIDENCE
    ranges = payload.line_ranges.get(finding.file_path)
    if finding.file_path not in payload.paths or not ranges:
        return REASON_PATH_NOT_ALLOWED
    if finding.start_line < 1 or finding.end_line < finding.start_line:
        return REASON_LINE_RANGE
    inside = any(
        start <= finding.start_line and finding.end_line <= end
        for start, end in ranges
    )
    if not inside:
        return REASON_LINE_RANGE
    if _agent_dedup_key(finding) in seen:
        return REASON_DUPLICATE
    return None


def _agent_dedup_key(finding: ReviewFinding) -> tuple:
    return (
        finding.file_path,
        finding.start_line,
        finding.end_line,
        finding.rule_id.strip().lower(),
        finding.title.strip().lower(),
        finding.category,
    )


def _validate_static_findings(
    payload: AgentContextPayload | None,
    findings: list[StaticAnalysisFinding],
) -> tuple[list[StaticAnalysisFinding], dict[str, int], int, dict[str, int]]:
    dropped: dict[str, int] = {}
    unverified_reasons: dict[str, int] = {}
    kept: list[StaticAnalysisFinding] = []
    seen: set[tuple] = set()
    for finding in findings:
        if not _static_is_valid(finding):
            dropped[REASON_INVALID_STATIC] = (
                dropped.get(REASON_INVALID_STATIC, 0) + 1
            )
            continue
        key = _static_dedup_key(finding)
        if key in seen:
            dropped[REASON_DUPLICATE] = dropped.get(REASON_DUPLICATE, 0) + 1
            continue
        seen.add(key)
        kept.append(finding)
        reason = _static_verification(payload, finding)
        if reason is not None:
            unverified_reasons[reason] = (
                unverified_reasons.get(reason, 0) + 1
            )
    unverified = sum(unverified_reasons.values())
    return kept, dropped, unverified, unverified_reasons


def _static_is_valid(finding: StaticAnalysisFinding) -> bool:
    """Hard invariants only; never requires LLM style evidence fields."""
    if not finding.rule_id.strip() or not finding.message.strip():
        return False
    if not is_repo_relative_path(finding.file_path):
        return False
    return finding.start_line >= 1 and finding.end_line >= finding.start_line


def _static_dedup_key(finding: StaticAnalysisFinding) -> tuple:
    return (
        finding.tool,
        finding.file_path,
        finding.start_line,
        finding.end_line,
        finding.rule_id.strip().lower(),
        finding.category,
    )


def _static_verification(
    payload: AgentContextPayload | None,
    finding: StaticAnalysisFinding,
) -> str | None:
    """None when the payload covers the finding, else a safe reason code."""
    if payload is None or not payload.available:
        return UNVERIFIED_NO_PAYLOAD
    ranges = payload.line_ranges.get(finding.file_path)
    if not ranges:
        return UNVERIFIED_NOT_IN_PAYLOAD
    inside = any(
        start <= finding.start_line and finding.end_line <= end
        for start, end in ranges
    )
    return None if inside else UNVERIFIED_NOT_IN_PAYLOAD


def _anchor_counts(
    entries: list[tuple[str, int, int]],
    changed_ranges,
) -> tuple[int, int, int]:
    """Classify findings against the diff changed lines (measurement only).

    Returns (anchored, not_on_changed_lines, anchor_unknown). A finding
    whose range intersects a changed range of its file is anchored; a
    finding whose file has changed ranges but no intersection is counted
    as not_on_changed_lines; a file without changed-line information
    (including no changed_ranges at all) counts as anchor_unknown. The
    classification never drops or rewrites a finding.
    """
    if not changed_ranges:
        return 0, 0, len(entries)
    anchored = 0
    not_on_changed = 0
    unknown = 0
    for file_path, start_line, end_line in entries:
        ranges = changed_ranges.get(file_path)
        if not ranges:
            unknown += 1
            continue
        intersects = any(
            range_start <= end_line and start_line <= range_end
            for range_start, range_end in ranges
        )
        if intersects:
            anchored += 1
        else:
            not_on_changed += 1
    return anchored, not_on_changed, unknown