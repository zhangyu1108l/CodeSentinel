"""Bounded code context payload for finding agents (Phase 8.4).

Builds the analysis payload handed to an agent from the already assembled
CodeContext (Phase 6) and any available static analysis findings. It
reuses render_code_context, so the payload keeps the Phase 6.6 budget
semantics, and it adds its own hard bounds: file count, total characters
and static finding count. Paths and the line ranges that actually exist
in the payload are kept, so findings can be verified against them.

The payload is prompt material: it embeds untrusted source and must never
be logged. This module only logs counts.
"""

import logging
from collections.abc import Sequence

from pydantic import BaseModel, Field

from app.prompts.code_context import render_code_context
from app.prompts.static_analysis import render_static_findings_lines
from app.schemas.code_context import CodeContext, FileContext
from app.schemas.static_analysis import StaticAnalysisFinding

logger = logging.getLogger("codesentinel-ai.agent_context_payload")

DEFAULT_MAX_FILES = 20
DEFAULT_MAX_TOTAL_CHARS = 24000
DEFAULT_MAX_STATIC_FINDINGS = 50
MAX_STATIC_MESSAGE_CHARS = 300


class AgentContextPayload(BaseModel):
    """Bounded, verifiable context for one finding agent run."""

    available: bool = False
    reason: str | None = None
    repository: str = ""
    pr_number: int = 0
    commit_sha: str | None = None
    code_section: str = ""
    static_section: str = ""
    paths: list[str] = Field(default_factory=list)
    line_ranges: dict[str, list[tuple[int, int]]] = Field(
        default_factory=dict
    )
    files_included: int = 0
    files_dropped: int = 0
    static_findings_included: int = 0
    static_findings_dropped: int = 0
    truncated: bool = False
    notes: list[str] = Field(default_factory=list)


def build_agent_context(
    code_context: CodeContext | None,
    static_findings: Sequence[StaticAnalysisFinding] = (),
    max_files: int = DEFAULT_MAX_FILES,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
    max_static_findings: int = DEFAULT_MAX_STATIC_FINDINGS,
) -> AgentContextPayload:
    """Build the bounded payload for one agent run.

    Returns available=False when no CodeContext exists; callers must not
    fabricate findings in that case. Files are included in context order
    and dropped from the end when the character budget is exceeded.
    """
    if max_files <= 0:
        raise ValueError("max_files must be greater than 0")
    if max_total_chars <= 0:
        raise ValueError("max_total_chars must be greater than 0")
    if max_static_findings < 0:
        raise ValueError("max_static_findings must not be negative")

    if code_context is None:
        return AgentContextPayload(
            available=False, reason="context_unavailable"
        )

    included = list(code_context.files)[:max_files]
    files_dropped = len(code_context.files) - len(included)

    static_section, static_included, static_dropped = _render_static(
        static_findings, max_static_findings
    )

    truncated = files_dropped > 0
    code_section = _render_code(code_context, included)
    while included and (
        len(code_section) + len(static_section) > max_total_chars
    ):
        included = included[:-1]
        files_dropped += 1
        truncated = True
        code_section = _render_code(code_context, included)

    combined = code_section + static_section
    if len(combined) > max_total_chars:
        combined = combined[:max_total_chars]
        static_section = ""
        code_section = combined
        truncated = True

    paths: list[str] = []
    line_ranges: dict[str, list[tuple[int, int]]] = {}
    for file_context in included:
        ranges = _line_ranges_for(file_context)
        if not ranges:
            continue
        paths.append(file_context.file_diff.path)
        line_ranges[file_context.file_diff.path] = ranges

    notes = list(code_context.notes)
    if files_dropped:
        notes.append(
            f"context payload dropped {files_dropped} file(s) to fit "
            "the payload limits"
        )
    if truncated:
        notes.append(
            "context payload was truncated to fit the payload limits"
        )

    if not included:
        reason = "context_empty"
    elif not paths:
        reason = "no_reportable_lines"
    else:
        reason = None

    payload = AgentContextPayload(
        available=reason is None,
        reason=reason,
        repository=code_context.repository,
        pr_number=code_context.pr_number,
        commit_sha=code_context.head_sha,
        code_section=code_section,
        static_section=static_section,
        paths=paths,
        line_ranges=line_ranges,
        files_included=len(included),
        files_dropped=files_dropped,
        static_findings_included=static_included,
        static_findings_dropped=static_dropped,
        truncated=truncated,
        notes=notes,
    )
    logger.debug(
        "Agent context payload built: files=%d, dropped=%d, "
        "static_findings=%d, chars=%d, truncated=%s",
        payload.files_included,
        payload.files_dropped,
        payload.static_findings_included,
        len(payload.code_section) + len(payload.static_section),
        payload.truncated,
    )
    return payload


def _render_code(
    code_context: CodeContext, files: list[FileContext]
) -> str:
    if not files:
        return ""
    subset = code_context.model_copy(
        update={"files": files, "stats": None, "truncation": None}
    )
    return render_code_context(subset)


def _render_static(
    findings: Sequence[StaticAnalysisFinding], limit: int
) -> tuple[str, int, int]:
    section = render_static_findings_lines(
        findings,
        max_findings=limit,
        max_message_chars=MAX_STATIC_MESSAGE_CHARS,
    )
    included = min(len(findings), limit)
    return section, included, len(findings) - included


def _line_ranges_for(
    file_context: FileContext,
) -> list[tuple[int, int]]:
    """Line ranges that exist in this payload for the file."""
    if file_context.content_available and file_context.line_count > 0:
        return [(1, file_context.line_count)]

    ranges = [
        (item.start_line, item.end_line)
        for item in file_context.file_diff.changed_ranges
    ]
    ranges.extend(
        (method.start_line, method.end_line)
        for method in file_context.methods
    )
    ranges.extend(
        (item.start_line, item.end_line)
        for item in file_context.related_code
    )
    return _merge_ranges(ranges)


def _merge_ranges(
    ranges: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if start > end or start < 1:
            continue
        if merged and start <= merged[-1][1] + 1:
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return merged