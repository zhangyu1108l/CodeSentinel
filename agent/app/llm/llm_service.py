import json
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.deepseek_client import DeepSeekClient
from app.llm.exceptions import LLMResponseError
from app.schemas.llm_output import LlmReviewOutput
from app.schemas.review import ReviewFinding
from app.schemas.validation import validation_error_summary

logger = logging.getLogger("codesentinel-ai.llm_service")

ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMService:
    """Orchestrates LLM calls and validates structured output.

    Flow: DeepSeek raw content (str) -> json.loads -> LlmReviewOutput
    -> list[ReviewFinding]. Parse or schema failures raise LLMResponseError.
    """

    def __init__(self, deepseek_client: DeepSeekClient = None):
        self.deepseek_client = deepseek_client or DeepSeekClient()

    async def generate_findings(
        self, messages: list[dict]
    ) -> list[ReviewFinding]:
        output = await self.generate_structured(messages, LlmReviewOutput)
        logger.info("LLM generated %d findings", len(output.findings))
        return output.findings

    async def generate_structured(
        self, messages: list[dict], schema: type[ModelT]
    ) -> ModelT:
        """Call the LLM once and validate its JSON output against schema.

        Exactly one DeepSeek call is made per invocation; parse or schema
        failures raise LLMResponseError without embedding the raw output.
        """
        content = await self.deepseek_client.chat(messages)

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("LLM returned invalid JSON: %s", e)
            raise LLMResponseError(f"LLM returned invalid JSON: {e}") from e

        try:
            return schema.model_validate(data)
        except ValidationError as error:
            summary = validation_error_summary(error)
            logger.error(
                "LLM output failed schema validation: %s", summary
            )
            raise LLMResponseError(
                f"LLM output failed schema validation: {summary}"
            ) from None
