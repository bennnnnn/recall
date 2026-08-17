from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.core.db import SessionLocal
from app.core.redis import get_redis_client

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness — process is up. Do not couple this to Redis or Postgres."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> dict[str, str]:
    """Readiness — Postgres can take traffic.

    Redis is reported but not required. A Redis blip must not drain the Fly
    fleet; chat/quota already fail closed per request.
    """
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        # Don't leak the underlying exception text (it may include connection
        # strings or internal details) — just signal not ready.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dependency check failed",
        ) from None
    redis_status = "ok"
    try:
        await get_redis_client().ping()
    except Exception:
        redis_status = "degraded"
    return {"status": "ok", "redis": redis_status}
