from pydantic import BaseModel

from app.schemas.review import ReviewFinding


class LlmReviewOutput(BaseModel):
    """Structured output contract for LLM review responses.

    The LLM only produces findings. task_id, status and report are
    assembled by ReviewService.
    """

    findings: list[ReviewFinding]
