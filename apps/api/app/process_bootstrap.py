"""Shared API/worker process initialization and worker runtime wiring."""

import asyncio

from app.background import (
    billing_reconcile_scheduler,
    email_reminder_scheduler,
    push_scheduler,
)
from app.background import handlers as job_handlers
from app.content.legal import warn_if_no_support_email
from app.core import jobs, shutdown
from app.core.background_tasks import drain_background_tasks
from app.core.config import Settings, validate_production_settings
from app.core.db import engine, warmup_db_pool
from app.core.logging import setup_logging
from app.core.redis import get_redis_client
from app.core.sentry import init_sentry
from app.core.sympy_executor import shutdown_sympy_executor
from app.gateways import email_gateway
from app.gateways.http_client import aclose_pooled_clients
from app.modules.attachments import reaper as attachment_orphan_reaper
from app.modules.chat.finalize_registry import stop_inflight_streams
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
    warn_if_no_support_email(settings)
    email_gateway.warn_if_unavailable(settings)
    role = validate_process_role(settings)
    setup_mcp_adapters(settings)
    await warmup_db_pool()
    if role in ("all", "api"):
        from app.core.sympy_executor import warm_sympy_pool
        from app.modules.math.sympy_warmup import warm_math_worker

        await warm_sympy_pool(warm_math_worker)
        install_chat_stop_on_signal()


def install_chat_stop_on_signal() -> None:
    """At SIGINT/SIGTERM, stop in-flight chat turns the way the user's Stop does.

    uvicorn only runs the lifespan shutdown after its graceful wait; by then the
    machine is about to be killed. Stopped at the signal, each partial reply is
    saved and its chat's prepare lock released inside that wait (deploy: Fly
    ``kill_timeout`` 45s, uvicorn ``--timeout-graceful-shutdown`` 30s).
    """
    shutdown.on_stop(stop_inflight_streams)
    shutdown.install_signal_hook(asyncio.get_running_loop())


async def start_worker_runtime(settings: Settings) -> None:
    job_handlers.register_all()
    await jobs.start_worker(settings)
    await push_scheduler.start_push_scheduler(settings)
    await email_reminder_scheduler.start_email_reminder_scheduler(settings)
    await attachment_orphan_reaper.start_orphan_reaper(settings)
    await billing_reconcile_scheduler.start_billing_reconcile_scheduler(settings)


async def stop_worker_runtime() -> None:
    await jobs.stop_worker()
    await push_scheduler.stop_push_scheduler()
    await email_reminder_scheduler.stop_email_reminder_scheduler()
    await attachment_orphan_reaper.stop_orphan_reaper()
    await billing_reconcile_scheduler.stop_billing_reconcile_scheduler()


async def shutdown_process(
    *,
    stop_worker: bool,
    drain_before_stop: bool = True,
) -> None:
    # Already done at the signal when the hook is installed; a no-op then.
    shutdown.begin_stop()
    if stop_worker and not drain_before_stop:
        await stop_worker_runtime()
    await drain_background_tasks(timeout_seconds=10.0)
    if stop_worker and drain_before_stop:
        await stop_worker_runtime()
    shutdown_sympy_executor()
    await engine.dispose()
    await get_redis_client().aclose()
    await aclose_pooled_clients()
