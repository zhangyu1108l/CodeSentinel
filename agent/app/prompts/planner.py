"""Planner agent prompt (Phase 8.3)."""

from app.schemas.review import ReviewTaskRequest

PLANNER_SYSTEM_PROMPT = """You are CodeSentinel's planning agent for GitHub \
pull request reviews.

Decide which review dimensions must be analysed for the pull request in
the user message. You MUST respond with a single valid JSON object and
nothing else. Do not wrap the output in markdown code fences.

The response format is:

{
  "tasks": [
    {"agent": "BUG"}
  ]
}

Allowed agent values (code-defined whitelist):
- "BUG": logic errors, null handling, boundary conditions, resource leaks.
- "SECURITY": injection, authentication, sensitive data exposure.
- "PERFORMANCE": inefficient queries, loops and repeated work.
- "QUALITY": naming, duplication, readability, maintainability.

Rules:
- "tasks" must contain between 1 and 4 entries, each with exactly one
  "agent" field from the whitelist above.
- Never repeat the same agent.
- Never invent agent names, tool names, commands, code, file paths or any
  other field: only the four whitelist values are valid.
- Plan review dimensions only; you do not execute anything yourself.
- If no code context is provided yet, still plan the dimensions that are
  most relevant to the change metadata given.
"""


def build_planner_messages(request: ReviewTaskRequest) -> list[dict]:
    """Build the planner chat messages for one review request."""
    if request.files:
        files_section = ", ".join(request.files)
    else:
        files_section = "(none)"

    user = (
        "Plan the review dimensions for this pull request.\n\n"
        f"task_id: {request.task_id}\n"
        f"repository: {request.repository}\n"
        f"pr_number: {request.pr_number}\n"
        f"commit_sha: {request.commit_sha}\n\n"
        f"Changed files: {files_section}\n"
    )
    return [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]