from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import process_bootstrap
from app.core.config import cors_allow_origins, get_settings
from app.core.request_id import RequestIdMiddleware
from app.core.rest_rate_limit import RestRateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.routers import (
    admin,
    analytics,
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
    settings = get_settings()
    await process_bootstrap.initialize_process(settings)
    role = process_bootstrap.validate_process_role(settings)
    if role in ("all", "worker"):
        await process_bootstrap.start_worker_runtime(settings)
    yield
    await process_bootstrap.shutdown_process(stop_worker=role in ("all", "worker"))


def create_app() -> FastAPI:
    settings = get_settings()
    # Hide OpenAPI/Swagger on production — reduces scanner surface. Dev/staging
    # keep /docs for local exploration.
    docs_enabled = settings.environment != "production"
    app = FastAPI(
        title="Recall API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    cors_origins = cors_allow_origins(settings)
    # Middleware is outermost-last: rate-limit must sit *inside* CORS so a 429
    # still gets Access-Control-* headers (browsers otherwise report a network
    # error). Security headers wrap the whole stack last.
    app.add_middleware(RestRateLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        # Credentials cannot be used with wildcard origins; only enable when
        # an explicit allow-list is configured (prod requires that).
        allow_credentials=cors_origins != ["*"],
        # Explicit method/header allowlists — `["*"]` here reflects every
        # method/header the client might use and lets the browser block the
        # rest, instead of echoing whatever the client sends.
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
    )
    # Baseline security headers (nosniff / no-frame / no-referrer / HSTS in
    # production behind TLS). Added last so it wraps the whole stack on the
    # way out; per-route headers that already set one are not overridden.
    app.add_middleware(
        SecurityHeadersMiddleware,
        enable_hsts=settings.environment == "production",
    )

    app.include_router(health.router)
    app.include_router(legal.router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(analytics.router)
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
