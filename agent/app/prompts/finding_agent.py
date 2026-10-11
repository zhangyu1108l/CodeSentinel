"""Dimension specific finding agent prompt (Phase 8.3)."""

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
  code content; if nothing can be analysed, return {{"findings": []}}.
- Never report a file_path that was not provided; never invent a line
  number.
- Write all finding fields in English.
"""


def build_finding_agent_messages(
    request: ReviewTaskRequest, category: Category
) -> list[dict]:
    """Build the finding agent chat messages for one dimension."""
    if request.files:
        files_section = ", ".join(request.files)
    else:
        files_section = "(none)"

    user = (
        f"Run the {category.value} analysis for this pull request.\n\n"
        f"task_id: {request.task_id}\n"
        f"repository: {request.repository}\n"
        f"pr_number: {request.pr_number}\n"
        f"commit_sha: {request.commit_sha}\n\n"
        f"Changed files: {files_section}\n\n"
        "Note: no file content or diff is attached yet. If there is "
        'nothing to analyse, return {"findings": []}.'
    )
    return [
        {
            "role": "system",
            "content": _AGENT_SYSTEM_TEMPLATE.format(
                category=category.value
            ),
        },
        {"role": "user", "content": user},
    ]