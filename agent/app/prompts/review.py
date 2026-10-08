from app.prompts.code_context import (
    render_code_context,
    render_context_unavailable,
)
from app.schemas.code_context import CodeContext
from app.schemas.review import ReviewTaskRequest

LEGACY_NOTE = (
    "Note: no file content or diff is provided for this review. "
    "Analyze only the information provided above."
)

SYSTEM_PROMPT = """You are CodeSentinel, an AI code review engine for \
GitHub pull requests.

Analyze the pull request described in the user message and report code review
findings. You MUST respond with a single valid JSON object and nothing else.
Do not wrap the output in markdown code fences.

The response format is:

{
  "findings": [
    {
      "category": "BUG",
      "severity": "HIGH",
      "confidence": 0.9,
      "rule_id": "string",
      "title": "string",
      "file_path": "string",
      "start_line": 1,
      "end_line": 1,
      "description": "string",
      "reason": "string",
      "suggestion": "string",
      "references": ["string"]
    }
  ]
}

Field constraints:
- "category" must be one of: BUG, SECURITY, PERFORMANCE, QUALITY.
- "severity" must be one of: CRITICAL, HIGH, MEDIUM, LOW, INFO.
- "confidence" must be a number between 0.0 and 1.0.
- "start_line" and "end_line" must be positive integers.
- "references" must be a list of strings (empty list is allowed).

Rules:
- If no real issue is found, return {"findings": []}.
- If no code content is provided, there is nothing to analyze: return
  {"findings": []}.
- Never fabricate findings. Only report issues supported by concrete evidence
  in the provided code content.
- Every finding must reference a "file_path" that is listed in the changed
  files or in the provided code context. Never report a file that was not
  provided.
- "start_line" and "end_line" must be lines that exist in the provided diff
  or code for that file, on the head revision. Never invent a line number.
  If the exact line cannot be determined from the provided context, anchor
  the finding to the nearest changed line that is provided.
- When a file is marked as content unavailable, or the context is marked as
  truncated, analyze only what is shown: missing code is not evidence of
  absence of issues.
- Write all finding field values in English.
"""


def build_messages(
    request: ReviewTaskRequest,
    context: CodeContext | None = None,
    context_report: dict | None = None,
) -> list[dict]:
    """Build the chat messages for a review request.

    context is the assembled, budgeted CodeContext (or None) and
    context_report is the small status dict produced by ReviewService
    ({"available": bool, "degraded": bool, "reason": str | None}).

    Three shapes are produced:
    - no report (direct legacy callers): the Phase 5.2 user message,
      unchanged, note included;
    - context available: the rendered CodeContext is appended, carrying
      the diff, the changed method slices, the related code and an
      explicit statement about unavailable content and truncation;
    - context degraded: the prompt states that the PR context is
      unavailable and never fabricates code.

    Content is only rendered from the provided context; nothing is
    invented when a file or the whole context is missing.
    """
    if request.files:
        files_section = ", ".join(request.files)
    else:
        files_section = "(none)"

    header = (
        "Review the following GitHub pull request.\n\n"
        f"task_id: {request.task_id}\n"
        f"repository: {request.repository}\n"
        f"pr_number: {request.pr_number}\n"
        f"commit_sha: {request.commit_sha}\n\n"
        f"Changed files: {files_section}\n\n"
    )

    if (
        context_report is not None
        and context_report.get("available")
        and context is not None
    ):
        tail = render_code_context(context)
    elif context_report is not None and context_report.get("degraded"):
        tail = render_context_unavailable(context_report.get("reason"))
    else:
        tail = LEGACY_NOTE

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": header + tail},
    ]
