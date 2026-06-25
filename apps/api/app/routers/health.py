from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.redis import get_redis_client

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> dict[str, str]:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        redis = get_redis_client()
        await redis.ping()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Dependency check failed: {exc}",
        ) from exc
    return {"status": "ok"}
