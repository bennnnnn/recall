"""Tiny HTTP health server for the standalone worker process.

The worker (`app/worker_main.py`) has no HTTP surface, so Fly can't tell a
crashed worker from one whose event loop is blocked/deadlocked. This exposes a
single `/health/ready` endpoint (on `settings.worker_health_port`) that reports
ready only when Redis is reachable AND the job-loop task is alive — letting Fly
auto-restart a stuck worker. It is NOT mounted on the main API app.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from app.core import jobs
from app.core.redis import get_redis_client


def create_worker_health_app() -> FastAPI:
    app = FastAPI(title="Recall Worker Health")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready() -> dict[str, str]:
        if not jobs.is_worker_alive():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="worker loop not running",
            )
        try:
            await get_redis_client().ping()
        except Exception:
            # Don't leak connection details — just signal not ready.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Dependency check failed",
            ) from None
        return {"status": "ok"}

    return app
