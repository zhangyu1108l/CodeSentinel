import logging
from typing import Optional

import httpx

from app.config.settings import settings
from app.llm.exceptions import LLMConfigError, LLMException

logger = logging.getLogger("codesentinel-ai.deepseek_client")


class DeepSeekClient:
    """HTTP client for the DeepSeek OpenAI-compatible chat API.

    Pure transport layer: builds the request, handles authentication,
    timeouts and HTTP errors. Response parsing/validation lives in LLMService.
    """

    def __init__(
        self,
        base_url: str = settings.DEEPSEEK_BASE_URL,
        api_key: str = settings.DEEPSEEK_API_KEY,
        model: str = settings.DEEPSEEK_MODEL,
        timeout: float = settings.DEEPSEEK_TIMEOUT,
        temperature: float = settings.DEEPSEEK_TEMPERATURE,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature

    async def chat(self, messages: list[dict]) -> str:
        if not self.api_key:
            raise LLMConfigError("DEEPSEEK_API_KEY is not configured")

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": self.temperature,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                body = resp.json()
                content: Optional[str] = body["choices"][0]["message"]["content"]
                if not content:
                    raise LLMException("DeepSeek returned empty message content")
                logger.info(
                    "DeepSeek responded: model=%s, content_length=%d",
                    self.model,
                    len(content),
                )
                return content
        except httpx.TimeoutException as e:
            logger.error(
                "DeepSeek request timed out after %ss: %s", self.timeout, e
            )
            raise LLMException(
                f"DeepSeek request timed out after {self.timeout}s"
            ) from e
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(
                "DeepSeek API error (HTTP %d): %s",
                status_code,
                e.response.text[:500],
            )
            raise LLMException(
                f"DeepSeek API error: HTTP {status_code}"
            ) from e
        except LLMException:
            raise
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            logger.error("DeepSeek call failed: %s", e)
            raise LLMException(f"DeepSeek call failed: {e}") from e
