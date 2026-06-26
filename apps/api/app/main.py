from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import jobs
from app.core.config import get_settings, validate_production_settings
from app.core.db import engine
from app.core.logging import setup_logging
from app.core.redis import get_redis_client
from app.routers import auth, chats, health, link_preview, memories, models, ws


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    settings = get_settings()
    validate_production_settings(settings)
    await jobs.start_worker(settings)
    yield
    await jobs.stop_worker()
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
    app.include_router(link_preview.router)
    app.include_router(chats.router)
    app.include_router(memories.router)
    app.include_router(models.router)
    app.include_router(ws.router)

    return app


app = create_app()
