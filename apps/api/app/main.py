from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.background import attachment_orphan_reaper, gmail_periodic_sync, push_scheduler
from app.core import jobs
from app.core.config import get_settings, validate_production_settings
from app.core.db import engine, warmup_db_pool
from app.core.logging import setup_logging
from app.core.redis import get_redis_client
from app.core.request_id import RequestIdMiddleware
from app.core.rest_rate_limit import RestRateLimitMiddleware
from app.core.sentry import init_sentry
from app.gateways.http_client import aclose_pooled_clients
from app.routers import (
    admin,
    attachments,
    auth,
    chat_stream,
    chats,
    gmail_integrations,
    health,
    home,
    images,
    integrations,
    legal,
    link_preview,
    memories,
    models,
    projects,
    search,
    speech,
    suggestions,
    todos,
    users,
    webhooks,
    ws,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    settings = get_settings()
    init_sentry(settings)
    validate_production_settings(settings)
    from app.gateways.mcp import setup_mcp_adapters

    setup_mcp_adapters(settings)
    await warmup_db_pool()
    role = settings.process_role.strip().lower()
    if role in ("all", "worker"):
        await jobs.start_worker(settings)
        await push_scheduler.start_push_scheduler(settings)
        await gmail_periodic_sync.start_gmail_periodic_scheduler(settings)
        await attachment_orphan_reaper.start_orphan_reaper(settings)
    yield
    if role in ("all", "worker"):
        await jobs.stop_worker()
        await push_scheduler.stop_push_scheduler()
        await gmail_periodic_sync.stop_gmail_periodic_scheduler()
        await attachment_orphan_reaper.stop_orphan_reaper()
    await engine.dispose()
    await get_redis_client().aclose()
    await aclose_pooled_clients()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Recall API", version="0.1.0", lifespan=lifespan)

    cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=bool(cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RestRateLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)

    app.include_router(health.router)
    app.include_router(legal.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(webhooks.router)
    app.include_router(users.router)
    app.include_router(home.router)
    app.include_router(link_preview.router)
    app.include_router(chats.router)
    app.include_router(chat_stream.router)
    app.include_router(memories.router)
    app.include_router(models.router)
    app.include_router(todos.router)
    app.include_router(projects.router)
    app.include_router(search.router)
    app.include_router(suggestions.router)
    app.include_router(attachments.router)
    app.include_router(integrations.router)
    app.include_router(gmail_integrations.router)
    app.include_router(speech.router)
    app.include_router(images.router)
    app.include_router(ws.router)

    return app


app = create_app()
