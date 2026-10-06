import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.review_router import router as review_router
from app.config.settings import settings

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(settings.APP_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{settings.APP_NAME} starting on {settings.APP_HOST}:{settings.APP_PORT}")
    yield
    logger.info(f"{settings.APP_NAME} shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(review_router)


@app.get("/health")
async def health():
    return {
        "status": "UP",
        "service": settings.APP_NAME,
    }