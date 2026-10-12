"""Static analysis evidence rendering for prompts (Phase 8.6).

Shared renderer for deterministic tool findings: used by the general
review prompt and by the bounded agent context payload. It renders only
metadata (tool, rule, severity/category, path, lines and a truncated
message) and never raw tool output or source code.
"""

from collections.abc import Sequence

from app.schemas.static_analysis import StaticAnalysisFinding

DEFAULT_MAX_FINDINGS = 20
DEFAULT_MAX_MESSAGE_CHARS = 200


def render_static_findings_lines(
    findings: Sequence[StaticAnalysisFinding],
    max_findings: int = DEFAULT_MAX_FINDINGS,
    max_message_chars: int = DEFAULT_MAX_MESSAGE_CHARS,
) -> str:
    """Render up to max_findings finding lines (no omission note)."""
    selected = list(findings)[:max_findings]
    lines = []
    for finding in selected:
        message = finding.message[:max_message_chars]
        lines.append(
            f"- [{finding.tool.value}] {finding.rule_id} "
            f"({finding.severity.value}/{finding.category.value}) "
            f"{finding.file_path}:{finding.start_line}-"
            f"{finding.end_line}: {message}"
        )
    return "\n".join(lines)


def render_static_findings(
    findings: Sequence[StaticAnalysisFinding],
    max_findings: int = DEFAULT_MAX_FINDINGS,
    max_message_chars: int = DEFAULT_MAX_MESSAGE_CHARS,
) -> str:
    """Render finding lines plus an explicit omission note when capped."""
    section = render_static_findings_lines(
        findings,
        max_findings=max_findings,
        max_message_chars=max_message_chars,
    )
    dropped = max(0, len(findings) - max_findings)
    if dropped:
        note = f"- ... {dropped} more finding(s) omitted"
        section = f"{section}\n{note}" if section else note
    return section