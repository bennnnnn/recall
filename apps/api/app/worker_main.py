"""Background worker entrypoint — jobs + schedulers without HTTP."""

from __future__ import annotations

import asyncio
import logging

from app.background import attachment_orphan_reaper, gmail_periodic_sync, push_scheduler
from app.core import jobs
from app.core.config import get_settings, validate_production_settings
from app.core.db import engine
from app.core.logging import setup_logging
from app.core.redis import get_redis_client
from app.core.sentry import init_sentry
from app.gateways.mcp import setup_mcp_adapters


async def _run_worker() -> None:
    setup_logging()
    settings = get_settings()
    init_sentry(settings)
    validate_production_settings(settings)
    setup_mcp_adapters(settings)
    await jobs.start_worker(settings)
    await push_scheduler.start_push_scheduler(settings)
    await gmail_periodic_sync.start_gmail_periodic_scheduler(settings)
    await attachment_orphan_reaper.start_orphan_reaper(settings)
    logging.getLogger(__name__).info("Recall worker started (process_role=worker)")
    try:
        await asyncio.Event().wait()
    finally:
        await jobs.stop_worker()
        await push_scheduler.stop_push_scheduler()
        await gmail_periodic_sync.stop_gmail_periodic_scheduler()
        await attachment_orphan_reaper.stop_orphan_reaper()
        await engine.dispose()
        await get_redis_client().aclose()


def main() -> None:
    asyncio.run(_run_worker())


if __name__ == "__main__":
    main()
