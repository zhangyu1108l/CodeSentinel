class LLMException(Exception):
    """Base exception for LLM related errors."""


class LLMConfigError(LLMException):
    """Raised when the LLM configuration is missing or invalid."""


class LLMResponseError(LLMException):
    """Raised when the LLM response cannot be parsed or validated."""
