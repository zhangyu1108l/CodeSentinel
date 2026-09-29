import logging

from redis import Redis

from app.config.settings import settings
from app.worker.consumer import RedisTaskConsumer
from app.worker.handler import TaskHandler

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(settings.APP_NAME)


def main():
    logger.info("Starting worker, queue=%s", settings.REDIS_TASK_QUEUE)

    redis_client = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=False,
    )

    try:
        redis_client.ping()
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise SystemExit(1) from e

    handler = TaskHandler()
    consumer = RedisTaskConsumer(
        redis_client=redis_client,
        queue_key=settings.REDIS_TASK_QUEUE,
        handler=handler,
    )

    consumer.run()


if __name__ == "__main__":
    main()