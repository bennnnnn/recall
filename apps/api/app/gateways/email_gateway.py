"""Outbound transactional email gateway.

Provider is Resend (https://resend.com) when ``resend_api_key`` is configured.
With no key — the default in dev — :func:`send_email` logs the message instead
so the rest of the pipeline (job enqueue, templates, locale selection) is
exercised without any external account. Sending is best-effort: a failure is
logged and never raised into the caller (transactional email must not break
auth or the chat path).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


def is_configured(settings: Settings) -> bool:
    return bool(settings.resend_api_key.strip())


async def send_email(
    settings: Settings,
    *,
    to: str,
    subject: str,
    html: str,
    text: str,
) -> bool:
    """Send one transactional email. Returns True on success, False otherwise.

    Never raises — callers (background jobs) rely on this not propagating.
    """
    if not settings.email_enabled:
        logger.debug("Transactional email disabled; skipping to=%s subject=%r", to, subject)
        return False
    if not to.strip():
        logger.warning("Transactional email skipped: empty recipient")
        return False

    if not is_configured(settings):
        # Dev / no-provider path: log that the flow ran, but NOT the body —
        # transactional emails (welcome, receipts, reminders) contain PII and
        # recipient-specific content that shouldn't sit in INFO logs.
        logger.info("MOCK transactional email to=%s subject=%r chars=%d", to, subject, len(text))
        return True

    payload: dict[str, Any] = {
        "from": settings.email_from,
        "to": to,
        "subject": subject,
        "html": html,
        "text": text,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                settings.resend_api_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
        return True
    except Exception:
        logger.exception("Transactional email send failed to=%s subject=%r", to, subject)
        return False
