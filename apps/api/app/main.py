from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.background import gmail_periodic_sync, push_scheduler
from app.core import jobs
from app.core.config import get_settings, validate_production_settings
from app.core.db import SessionLocal, engine
from app.core.logging import setup_logging
from app.core.redis import get_redis_client
from app.routers import (
    auth,
    chats,
    health,
    home,
    link_preview,
    memories,
    models,
    projects,
    search,
    suggestions,
    templates,
    todos,
    ws,
)
from app.routers import integrations
from app.routers import attachments
from app.routers import gmail_integrations
from app.routers import users
from app.routers import webhooks
from app.services import seed_templates


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    settings = get_settings()
    validate_production_settings(settings)
    from app.gateways.mcp import setup_mcp_adapters

    setup_mcp_adapters(settings)
    await jobs.start_worker(settings)
    await push_scheduler.start_push_scheduler(settings)
    await gmail_periodic_sync.start_gmail_periodic_scheduler(settings)
    async with SessionLocal() as session:
        await seed_templates.seed_templates(session)
    yield
    await jobs.stop_worker()
    await push_scheduler.stop_push_scheduler()
    await gmail_periodic_sync.stop_gmail_periodic_scheduler()
    await engine.dispose()
    await get_redis_client().aclose()


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

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(webhooks.router)
    app.include_router(users.router)
    app.include_router(home.router)
    app.include_router(link_preview.router)
    app.include_router(chats.router)
    app.include_router(memories.router)
    app.include_router(models.router)
    app.include_router(todos.router)
    app.include_router(projects.router)
    app.include_router(search.router)
    app.include_router(suggestions.router)
    app.include_router(templates.router)
    app.include_router(attachments.router)
    app.include_router(integrations.router)
    app.include_router(gmail_integrations.router)
    app.include_router(ws.router)

    return app


app = create_app()
