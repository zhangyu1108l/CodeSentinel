from fastapi import APIRouter, Depends

from app.config.settings import settings
from app.context.pr_context_client import PrContextClient
from app.graph.workflow import ReviewWorkflow
from app.llm.llm_service import LLMService
from app.schemas.review import ReviewTaskRequest, ReviewTaskResult
from app.services.review_service import ReviewService
from app.services.static_analysis_service import StaticAnalysisService

router = APIRouter()


def get_llm_service() -> LLMService:
    return LLMService()


def get_pr_context_client() -> PrContextClient:
    return PrContextClient()


def get_static_analysis_service() -> StaticAnalysisService | None:
    """Production static analysis stage, disabled by configuration.

    Returns None when STATIC_ANALYSIS_ENABLED is false, in which case the
    review report keeps its pre Phase 8.6 shape. When enabled, the
    service is constructed with the configured executables and Semgrep
    config; a missing executable degrades to an explicit UNAVAILABLE
    tool result at run time instead of being silently skipped here.
    """
    if not settings.STATIC_ANALYSIS_ENABLED:
        return None
    return StaticAnalysisService(
        ruff_executable=settings.STATIC_ANALYSIS_RUFF_EXECUTABLE,
        bandit_executable=settings.STATIC_ANALYSIS_BANDIT_EXECUTABLE,
        semgrep_executable=settings.STATIC_ANALYSIS_SEMGREP_EXECUTABLE,
        semgrep_config_path=(
            settings.STATIC_ANALYSIS_SEMGREP_CONFIG or None
        ),
    )


def get_review_service(
    llm_service: LLMService = Depends(get_llm_service),
    pr_context_client: PrContextClient = Depends(get_pr_context_client),
    static_analysis_service: StaticAnalysisService | None = Depends(
        get_static_analysis_service
    ),
) -> ReviewService:
    return ReviewService(
        llm_service=llm_service,
        pr_context_client=pr_context_client,
        static_analysis_service=static_analysis_service,
    )


def get_review_workflow(
    review_service: ReviewService = Depends(get_review_service),
) -> ReviewWorkflow:
    return ReviewWorkflow(review_service=review_service)


@router.post("/api/reviews", response_model=ReviewTaskResult)
async def create_review(
    request: ReviewTaskRequest,
    workflow: ReviewWorkflow = Depends(get_review_workflow),
) -> ReviewTaskResult:
    return await workflow.run(request)