from fastapi import APIRouter, Depends

from app.context.pr_context_client import PrContextClient
from app.llm.llm_service import LLMService
from app.schemas.review import ReviewTaskRequest, ReviewTaskResult
from app.services.review_service import ReviewService

router = APIRouter()


def get_llm_service() -> LLMService:
    return LLMService()


def get_pr_context_client() -> PrContextClient:
    return PrContextClient()


def get_review_service(
    llm_service: LLMService = Depends(get_llm_service),
    pr_context_client: PrContextClient = Depends(get_pr_context_client),
) -> ReviewService:
    return ReviewService(
        llm_service=llm_service,
        pr_context_client=pr_context_client,
    )


@router.post("/api/reviews", response_model=ReviewTaskResult)
async def create_review(
    request: ReviewTaskRequest,
    service: ReviewService = Depends(get_review_service),
) -> ReviewTaskResult:
    return await service.review(request)