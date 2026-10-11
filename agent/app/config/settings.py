import math

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    APP_NAME: str = "codesentinel-ai"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_TIMEOUT: float = 60
    DEEPSEEK_TEMPERATURE: float = 0.1

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_TASK_QUEUE: str = "codesentinel:review:tasks"

    JAVA_SERVICE_URL: str = "http://localhost:8080"
    PR_CONTEXT_TIMEOUT: float = 30
    AI_SERVICE_URL: str = "http://localhost:8000"
    AI_SERVICE_TIMEOUT: float = 120
    REVIEW_TOTAL_BUDGET: float = 100
    REVIEW_TASK_MAX_RETRIES: int = 3

    STATIC_ANALYSIS_ENABLED: bool = True
    STATIC_ANALYSIS_RUFF_EXECUTABLE: str = "ruff"
    STATIC_ANALYSIS_BANDIT_EXECUTABLE: str = "bandit"
    STATIC_ANALYSIS_SEMGREP_EXECUTABLE: str = "semgrep"
    STATIC_ANALYSIS_SEMGREP_CONFIG: str = ""

    @model_validator(mode="after")
    def _validate_review_budget_against_worker_timeout(
        self,
    ) -> "Settings":
        """Startup guard for the review budget pair.

        REVIEW_TOTAL_BUDGET bounds the whole server side review while the
        worker stops waiting after AI_SERVICE_TIMEOUT; if the budget were
        equal or larger, the worker could abort while the AI service still
        runs, leaving orphan work and duplicate retries. A misconfigured
        pair fails here, at configuration initialization, instead of on
        the first request.
        """
        budget = self.REVIEW_TOTAL_BUDGET
        worker_timeout = self.AI_SERVICE_TIMEOUT
        if not math.isfinite(budget) or budget <= 0:
            raise ValueError(
                "REVIEW_TOTAL_BUDGET must be a positive finite number "
                f"(got {budget!r})"
            )
        if not math.isfinite(worker_timeout) or worker_timeout <= 0:
            raise ValueError(
                "AI_SERVICE_TIMEOUT must be a positive finite number "
                f"(got {worker_timeout!r})"
            )
        if budget >= worker_timeout:
            raise ValueError(
                "REVIEW_TOTAL_BUDGET must be strictly smaller than "
                "AI_SERVICE_TIMEOUT so the AI service finishes before "
                "the worker stops waiting "
                f"(REVIEW_TOTAL_BUDGET={budget!r}, "
                f"AI_SERVICE_TIMEOUT={worker_timeout!r})"
            )
        return self


settings = Settings()