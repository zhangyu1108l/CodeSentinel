import json
import logging

from pydantic import ValidationError

from app.llm.deepseek_client import DeepSeekClient
from app.llm.exceptions import LLMResponseError
from app.schemas.llm_output import LlmReviewOutput
from app.schemas.review import ReviewFinding

logger = logging.getLogger("codesentinel-ai.llm_service")


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
        content = await self.deepseek_client.chat(messages)

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("LLM returned invalid JSON: %s", e)
            raise LLMResponseError(f"LLM returned invalid JSON: {e}") from e

        try:
            output = LlmReviewOutput.model_validate(data)
        except ValidationError as e:
            logger.error("LLM output failed schema validation: %s", e)
            raise LLMResponseError(
                f"LLM output failed schema validation: {e}"
            ) from e

        logger.info("LLM generated %d findings", len(output.findings))
        return output.findings
