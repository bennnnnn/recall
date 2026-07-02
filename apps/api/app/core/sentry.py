"""Optional Sentry error reporting."""

from __future__ import annotations

import logging

from app.core.config import Settings

logger = logging.getLogger(__name__)
_initialized = False


def init_sentry(settings: Settings) -> None:
    global _initialized
    if _initialized or not settings.sentry_dsn.strip():
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("sentry-sdk not installed; skipping Sentry init")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn.strip(),
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        send_default_pii=False,
    )
    _initialized = True
    logger.info("Sentry initialized for environment=%s", settings.environment)
