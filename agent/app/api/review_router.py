from fastapi import APIRouter, Depends

from app.llm.llm_service import LLMService
from app.schemas.review import ReviewTaskRequest, ReviewTaskResult
from app.services.review_service import ReviewService

router = APIRouter()


def get_llm_service() -> LLMService:
    return LLMService()


def get_review_service(
    llm_service: LLMService = Depends(get_llm_service),
) -> ReviewService:
    return ReviewService(llm_service=llm_service)


@router.post("/api/reviews", response_model=ReviewTaskResult)
async def create_review(
    request: ReviewTaskRequest,
    service: ReviewService = Depends(get_review_service),
) -> ReviewTaskResult:
    return await service.review(request)
