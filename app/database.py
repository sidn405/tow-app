from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from app.config import settings
import redis.asyncio as redis

# Database engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool,
    future=True
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for models
Base = declarative_base()

# Redis connection
import redis.asyncio as redis
from typing import Optional

redis_client: Optional[redis.Redis] = None

def _normalize_redis_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith(("redis://", "rediss://", "unix://")):
        return url
    # if user accidentally set HOST:PORT[/db], fix it
    if url and "://" not in url:
        return f"redis://{url}"
    return url

async def init_redis():
    global redis_client
    url = _normalize_redis_url(settings.REDIS_URL)

    if not url.startswith(("redis://", "rediss://", "unix://")):
        raise ValueError(
            f"Invalid REDIS_URL: {url!r}. Must start with redis://, rediss://, or unix://"
        )

    redis_client = redis.from_url(url, decode_responses=True)
    # Fail fast with a clear reason if creds/network are wrong
    await redis_client.ping()

async def close_redis():
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None

async def get_redis():
    return redis_client
