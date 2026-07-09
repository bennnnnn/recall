"""Background worker entrypoint — jobs + schedulers without HTTP."""

from __future__ import annotations

import asyncio
import logging

from app.background import (
    attachment_orphan_reaper,
    email_reminder_scheduler,
    gmail_periodic_sync,
    push_scheduler,
)
from app.core import jobs
from app.core.config import get_settings, validate_production_settings
from app.core.db import engine
from app.core.logging import setup_logging
from app.core.redis import get_redis_client
from app.core.sentry import init_sentry
from app.gateways.mcp import setup_mcp_adapters
from app.worker_health import create_worker_health_app


async def _run_worker() -> None:
    setup_logging()
    settings = get_settings()
    init_sentry(settings)
    validate_production_settings(settings)
    setup_mcp_adapters(settings)
    await jobs.start_worker(settings)
    await push_scheduler.start_push_scheduler(settings)
    await email_reminder_scheduler.start_email_reminder_scheduler(settings)
    await gmail_periodic_sync.start_gmail_periodic_scheduler(settings)
    await attachment_orphan_reaper.start_orphan_reaper(settings)

    # Tiny health HTTP server so Fly can detect + restart a stuck worker.
    health_server = None
    health_task: asyncio.Task | None = None
    if settings.worker_health_port > 0:
        import uvicorn

        health_server = uvicorn.Server(
            uvicorn.Config(
                create_worker_health_app(),
                host="0.0.0.0",  # noqa: S104 - Fly requires binding to all interfaces
                port=settings.worker_health_port,
                log_level="warning",
                access_log=False,
            )
        )
        health_task = asyncio.create_task(health_server.serve())

    logging.getLogger(__name__).info("Recall worker started (process_role=worker)")
    try:
        await asyncio.Event().wait()
    finally:
        if health_server is not None:
            health_server.should_exit = True
            await health_server.shutdown()
        if health_task is not None:
            health_task.cancel()
            try:
                await health_task
            except asyncio.CancelledError:
                pass
        await jobs.stop_worker()
        await push_scheduler.stop_push_scheduler()
        await email_reminder_scheduler.stop_email_reminder_scheduler()
        await gmail_periodic_sync.stop_gmail_periodic_scheduler()
        await attachment_orphan_reaper.stop_orphan_reaper()
        await engine.dispose()
        await get_redis_client().aclose()


def main() -> None:
    asyncio.run(_run_worker())


if __name__ == "__main__":
    main()
