from pydantic import BaseModel, ConfigDict

from app.schemas.review import ReviewFinding


class LlmReviewOutput(BaseModel):
    """Structured output contract for LLM review responses.

    The LLM only produces findings. task_id, status and report are
    assembled by ReviewService. hide_input_in_errors is defense in depth
    because pydantic's default error display embeds an input preview.
    """

    model_config = ConfigDict(hide_input_in_errors=True)

    findings: list[ReviewFinding]
