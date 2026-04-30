import uuid
from redis.asyncio import Redis
from config.settings import settings
from utils.logger import get_logger

logger = get_logger("job_store")

_redis_client: Redis | None = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def create_job() -> str:
    redis = await get_redis()
    job_id = str(uuid.uuid4())
    await redis.hset(
        f"job:{job_id}",
        mapping={
            "status": "pending",
            "progress": "0",
            "message": "Job created",
        },
    )
    await redis.expire(f"job:{job_id}", 3600)
    logger.debug(f"Job created: {job_id}")
    return job_id


async def get_job(job_id: str) -> dict | None:
    redis = await get_redis()
    data = await redis.hgetall(f"job:{job_id}")
    return data if data else None


async def update_job(job_id: str, **kwargs) -> None:
    redis = await get_redis()
    await redis.hset(f"job:{job_id}", mapping={k: str(v) for k, v in kwargs.items()})
