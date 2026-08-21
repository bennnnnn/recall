"""Shared API/worker process initialization and worker runtime wiring."""

from app.background import (
    attachment_orphan_reaper,
    email_reminder_scheduler,
    gmail_periodic_sync,
    push_scheduler,
)
from app.background import handlers as job_handlers
from app.core import jobs
from app.core.background_tasks import drain_background_tasks
from app.core.config import Settings, validate_production_settings
from app.core.db import engine, warmup_db_pool
from app.core.logging import setup_logging
from app.core.redis import get_redis_client
from app.core.sentry import init_sentry
from app.gateways.http_client import aclose_pooled_clients
from app.services.mcp import setup_mcp_adapters

VALID_PROCESS_ROLES = frozenset({"all", "api", "worker"})


def validate_process_role(settings: Settings) -> str:
    role = settings.process_role.strip().lower()
    if role not in VALID_PROCESS_ROLES:
        raise RuntimeError(
            f"Invalid PROCESS_ROLE={settings.process_role!r}; "
            f"expected one of {sorted(VALID_PROCESS_ROLES)}"
        )
    return role


async def initialize_process(settings: Settings) -> None:
    setup_logging(json_output=settings.environment == "production")
    init_sentry(settings)
    validate_production_settings(settings)
    setup_mcp_adapters(settings)
    await warmup_db_pool()


async def start_worker_runtime(settings: Settings) -> None:
    job_handlers.register_all()
    await jobs.start_worker(settings)
    await push_scheduler.start_push_scheduler(settings)
    await email_reminder_scheduler.start_email_reminder_scheduler(settings)
    await gmail_periodic_sync.start_gmail_periodic_scheduler(settings)
    await attachment_orphan_reaper.start_orphan_reaper(settings)


async def stop_worker_runtime() -> None:
    await jobs.stop_worker()
    await push_scheduler.stop_push_scheduler()
    await email_reminder_scheduler.stop_email_reminder_scheduler()
    await gmail_periodic_sync.stop_gmail_periodic_scheduler()
    await attachment_orphan_reaper.stop_orphan_reaper()


async def shutdown_process(
    *,
    stop_worker: bool,
    drain_before_stop: bool = True,
) -> None:
    if stop_worker and not drain_before_stop:
        await stop_worker_runtime()
    await drain_background_tasks(timeout_seconds=10.0)
    if stop_worker and drain_before_stop:
        await stop_worker_runtime()
    await engine.dispose()
    await get_redis_client().aclose()
    await aclose_pooled_clients()
