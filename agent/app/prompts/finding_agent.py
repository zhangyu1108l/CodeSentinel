"""Dimension specific finding agent prompt (Phase 8.3/8.4)."""

from app.agents.context_payload import AgentContextPayload
from app.schemas.review import Category, ReviewTaskRequest

_AGENT_SYSTEM_TEMPLATE = """You are CodeSentinel's {category} analysis agent.

Analyse the pull request in the user message and report findings of the
"{category}" category only. You MUST respond with a single valid JSON
object and nothing else. Do not wrap the output in markdown code fences.

The response format is:

{{
  "findings": [
    {{
      "category": "{category}",
      "severity": "HIGH",
      "confidence": 0.0,
      "rule_id": "string",
      "title": "string",
      "file_path": "string",
      "start_line": 1,
      "end_line": 1,
      "description": "string",
      "reason": "string",
      "suggestion": "string",
      "references": ["string"]
    }}
  ]
}}

Rules:
- Every finding MUST use the "{category}" category; never report other
  categories.
- "severity" must be one of CRITICAL, HIGH, MEDIUM, LOW, INFO.
- "confidence" must be a number between 0.0 and 1.0.
- Never fabricate findings: report only issues supported by the provided
  code context or static analysis evidence; if nothing can be verified,
  return {{"findings": []}}.
- Never report a file_path or a line range that is not listed in the
  allowed finding locations; never invent a line number.
- Write all finding fields in English.
"""


def build_finding_agent_messages(
    request: ReviewTaskRequest,
    category: Category,
    context: AgentContextPayload | None = None,
) -> list[dict]:
    """Build the finding agent chat messages for one dimension."""
    if request.files:
        files_section = ", ".join(request.files)
    else:
        files_section = "(none)"

    header = (
        f"Run the {category.value} analysis for this pull request.\n\n"
        f"task_id: {request.task_id}\n"
        f"repository: {request.repository}\n"
        f"pr_number: {request.pr_number}\n"
        f"commit_sha: {request.commit_sha}\n\n"
        f"Changed files: {files_section}\n"
    )

    if context is not None and context.available:
        body = _context_block(context)
    else:
        body = (
            "\nNote: no file content or diff is attached yet. If there is "
            'nothing to analyse, return {"findings": []}.'
        )

    return [
        {
            "role": "system",
            "content": _AGENT_SYSTEM_TEMPLATE.format(
                category=category.value
            ),
        },
        {"role": "user", "content": header + body},
    ]


def _context_block(context: AgentContextPayload) -> str:
    block = (
        "\nCode context provided by CodeSentinel (read-only repository "
        "source at the reviewed revision; nothing was executed):\n\n"
        f"{context.code_section}\n"
    )
    if context.static_section:
        block += (
            "\nStatic analysis results already available (evidence from "
            "deterministic tools; validate before reporting):\n"
            f"{context.static_section}\n"
        )
    block += (
        "\nAllowed finding locations (only these file paths and line "
        "ranges exist in the provided context):\n"
        f"{_render_allowed_ranges(context)}\n"
        "\nHard constraints:\n"
        "- file_path must be one of the allowed paths above; start_line "
        "and end_line must both lie inside one listed range for that "
        "path.\n"
        "- Report only issues supported by the shown code or the static "
        "evidence; if nothing can be verified, return "
        '{"findings": []}.\n'
    )
    return block


def _render_allowed_ranges(context: AgentContextPayload) -> str:
    lines = []
    for path in context.paths:
        ranges = context.line_ranges.get(path, [])
        rendered = ", ".join(
            f"{start}-{end}" for start, end in ranges
        )
        lines.append(f"- {path}: {rendered}")
    return "\n".join(lines) if lines else "(none)"