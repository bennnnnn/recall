"""Optional Sentry error reporting."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.core.request_id import request_id_context

if TYPE_CHECKING:
    from sentry_sdk.types import Event, Hint

logger = logging.getLogger(__name__)
_initialized = False

# Client hangups are not application errors — they dominate the stream if
# captured at 100%. Keep real exceptions at full sample rate.
_IGNORED_EXC_TYPES = frozenset({"WebSocketDisconnect", "ClientDisconnect"})

_SENSITIVE_HEADER_NAMES = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-forwarded-authorization",
    }
)


def _exception_type_names(event: Event) -> list[str]:
    raw_exc = event.get("exception") or {}
    values = raw_exc.get("values") if isinstance(raw_exc, dict) else None
    names: list[str] = []
    for item in values or []:
        if isinstance(item, dict) and item.get("type"):
            names.append(str(item["type"]))
    return names


def _is_ignored(event: Event, hint: Hint) -> bool:
    exc_info = hint.get("exc_info") if isinstance(hint, dict) else None
    if exc_info and getattr(exc_info[0], "__name__", "") in _IGNORED_EXC_TYPES:
        return True
    return any(name in _IGNORED_EXC_TYPES for name in _exception_type_names(event))


def _scrub_headers(headers: object) -> None:
    if not isinstance(headers, dict):
        return
    for key in list(headers):
        if str(key).lower() in _SENSITIVE_HEADER_NAMES:
            headers[key] = "[REDACTED]"


def _scrub_request(request: object) -> None:
    """Drop bodies and secrets. Chat POSTs must never reach Sentry."""
    if not isinstance(request, dict):
        return
    request.pop("data", None)
    request.pop("cookies", None)
    request["query_string"] = ""
    _scrub_headers(request.get("headers"))
    env = request.get("env")
    if isinstance(env, dict):
        for key in list(env):
            lowered = str(key).lower()
            if lowered in {"http_authorization", "http_cookie"}:
                env[key] = "[REDACTED]"


def before_send(event: Event, hint: Hint) -> Event | None:
    """Filter noise and strip request bodies / auth headers before upload."""
    if _is_ignored(event, hint):
        return None
    _scrub_request(event.get("request"))
    request_id = request_id_context.get()
    if request_id:
        tags = event.setdefault("tags", {})
        if isinstance(tags, dict):
            tags["request_id"] = request_id
    return event


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
        before_send=before_send,
        ignore_errors=list(_IGNORED_EXC_TYPES),
    )
    _initialized = True
    logger.info("Sentry initialized for environment=%s", settings.environment)
