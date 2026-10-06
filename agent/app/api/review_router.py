from fastapi import APIRouter, Depends

from app.schemas.review import ReviewTaskRequest, ReviewTaskResult
from app.services.review_service import ReviewService

router = APIRouter()


def get_review_service() -> ReviewService:
    return ReviewService()


@router.post("/api/reviews", response_model=ReviewTaskResult)
async def create_review(
    request: ReviewTaskRequest,
    service: ReviewService = Depends(get_review_service),
) -> ReviewTaskResult:
    return service.review(request)
