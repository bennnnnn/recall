"""Background worker entrypoint — jobs + schedulers without HTTP."""

from __future__ import annotations

import asyncio
import logging

from app import process_bootstrap
from app.core.config import get_settings
from app.worker_health import create_worker_health_app


async def _run_worker() -> None:
    settings = get_settings()
    await process_bootstrap.initialize_process(settings)
    await process_bootstrap.start_worker_runtime(settings)

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
        await process_bootstrap.shutdown_process(
            stop_worker=True,
            drain_before_stop=False,
        )


def main() -> None:
    asyncio.run(_run_worker())


if __name__ == "__main__":
    main()
