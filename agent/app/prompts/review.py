from app.schemas.review import ReviewTaskRequest

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
- Write all finding field values in English.
"""


def build_messages(request: ReviewTaskRequest) -> list[dict]:
    """Build the chat messages for a review request.

    Phase 5.2 note: files only carries file paths and no code content or
    diff is provided yet, so a well-behaved model returns empty findings.
    """
    if request.files:
        files_section = ", ".join(request.files)
    else:
        files_section = "(none)"

    user_prompt = (
        "Review the following GitHub pull request.\n\n"
        f"task_id: {request.task_id}\n"
        f"repository: {request.repository}\n"
        f"pr_number: {request.pr_number}\n"
        f"commit_sha: {request.commit_sha}\n\n"
        f"Changed files: {files_section}\n\n"
        "Note: no file content or diff is provided for this review. "
        "Analyze only the information provided above."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
