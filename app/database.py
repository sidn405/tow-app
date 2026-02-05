from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from app.config import settings
import redis.asyncio as redis
from typing import Optional

def normalize_db_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url

# Database engine
engine = create_async_engine(
    normalize_db_url(settings.DATABASE_URL),
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

# ---- Redis (DO NOT CONNECT AT IMPORT TIME) ----
redis_client: Optional[redis.Redis] = None

def normalize_db_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url

def _normalize_redis_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith(("redis://", "rediss://", "unix://")):
        return url
    # If someone set HOST:PORT[/db], prepend scheme
    if url and "://" not in url:
        return f"redis://{url}"
    return url

async def init_redis() -> None:
    """Initialize Redis client (called on startup)."""
    global redis_client
    url = _normalize_redis_url(settings.REDIS_URL)

    if not url.startswith(("redis://", "rediss://", "unix://")):
        raise ValueError(
            f"REDIS_URL must start with redis://, rediss://, or unix://. Got: {url!r}"
        )

    redis_client = redis.from_url(url, decode_responses=True)
    # Fail fast if creds/host are wrong
    await redis_client.ping()

async def close_redis() -> None:
    """Close Redis client (called on shutdown)."""
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()  # aclose() is preferred in recent redis-py
        redis_client = None

# ---- Dependencies ----
async def get_db():
    """Dependency for getting database sessions"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_redis():
    """Dependency for getting Redis client"""
    if redis_client is None:
        # Optional: auto-init here, but better to init on startup
        raise RuntimeError("Redis not initialized. Did you call init_redis() on startup?")
    return redis_client

# ---- Lifecycle ----
async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def close_db():
    """Close database connections"""
    await engine.dispose()
    await close_redis()
