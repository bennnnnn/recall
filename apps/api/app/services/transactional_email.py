"""Transactional email content + dispatch (welcome, purchase receipts).

Templates are locale-aware via ``user.locale``. English is the source and the
fallback for any locale without a dedicated translation; the structure makes
adding more locales a data-only change. All dispatch goes through
``email_gateway.send_email`` and is best-effort.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings
from app.gateways import email_gateway
from app.models.orm import User
from app.services import locale as locale_service

logger = logging.getLogger(__name__)

# Locale codes supported by the mobile app (mirrors services/locale.py).
_SUPPORTED_LOCALES = frozenset(locale_service.LOCALE_NAMES.keys())


def _locale_for(user: User) -> str:
    code = locale_service.normalize_locale_code(getattr(user, "locale", None))
    return code if code in _SUPPORTED_LOCALES else "en"


def _display_name(user: User) -> str:
    name = (user.name or "").strip()
    return name if name else "there"


# ── templates ───────────────────────────────────────────────────────────────
# Each entry: {subject, text, html}. Keep copy short and plain-text-friendly.
# Only `en` is authored; other supported locales fall back to `en` for now —
# adding a locale is a matter of adding a key here, no code change needed.

_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "welcome": {
        "en": {
            "subject": "Welcome to Recall",
            "text": (
                "Hi {name},\n\n"
                "Welcome to Recall — your personal AI chat that remembers what "
                "matters to you. Ask it anything, jot down reminders, or start a "
                "learning project.\n\n"
                "A few things to try first:\n"
                "  - Connect your calendar or Gmail in Settings to surface events "
                "and email reminders.\n"
                "  - Tell Recall about yourself so its memory gets useful fast.\n"
                "  - Set your preferred language, tone, and response length in Settings.\n\n"
                "Cheers,\nThe Recall team"
            ),
            "html": (
                "<p>Hi {name},</p>"
                "<p>Welcome to <strong>Recall</strong> — your personal AI chat that "
                "remembers what matters to you. Ask it anything, jot down reminders, "
                "or start a learning project.</p>"
                "<p>A few things to try first:</p>"
                "<ul>"
                "<li>Connect your calendar or Gmail in Settings to surface events "
                "and email reminders.</li>"
                "<li>Tell Recall about yourself so its memory gets useful fast.</li>"
                "<li>Set your preferred language, tone, and response length in Settings.</li>"
                "</ul>"
                "<p>Cheers,<br/>The Recall team</p>"
            ),
        },
    },
    "receipt": {
        "en": {
            "subject": "Your Recall Pro receipt",
            "text": (
                "Hi {name},\n\n"
                "Thanks for subscribing to Recall Pro!\n\n"
                "Plan: Recall Pro\n"
                "{event_line}"
                "{expiration_line}"
                "\nYou can review or manage your subscription anytime from Settings "
                "in the app.\n\n"
                "Cheers,\nThe Recall team"
            ),
            "html": (
                "<p>Hi {name},</p>"
                "<p>Thanks for subscribing to <strong>Recall Pro</strong>!</p>"
                "<p>"
                "Plan: Recall Pro<br/>"
                "{event_line_html}"
                "{expiration_line_html}"
                "</p>"
                "<p>You can review or manage your subscription anytime from Settings "
                "in the app.</p>"
                "<p>Cheers,<br/>The Recall team</p>"
            ),
        },
    },
}


def _template(kind: str, locale: str) -> dict[str, str]:
    bundle = _TEMPLATES.get(kind, {})
    return bundle.get(locale) or bundle["en"]


def _render(template: str, **kwargs: Any) -> str:
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def build_welcome(user: User) -> tuple[str, str, str]:
    """Return (subject, html, text) for the welcome email."""
    locale = _locale_for(user)
    tpl = _template("welcome", locale)
    name = _display_name(user)
    return (
        tpl["subject"],
        _render(tpl["html"], name=name),
        _render(tpl["text"], name=name),
    )


def build_receipt(
    user: User,
    *,
    event_type: str,
    store: str | None = None,
    product_id: str | None = None,
    expiration: str | None = None,
) -> tuple[str, str, str]:
    """Return (subject, html, text) for a purchase/renewal receipt."""
    locale = _locale_for(user)
    tpl = _template("receipt", locale)
    name = _display_name(user)

    event_line = f"Event: {event_type}\n"
    if store:
        event_line += f"Store: {store}\n"
    if product_id:
        event_line += f"Product: {product_id}\n"
    expiration_line = f"Renews: {expiration}\n" if expiration else ""

    event_line_html = event_line.replace("\n", "<br/>")
    expiration_line_html = expiration_line.replace("\n", "<br/>")

    return (
        tpl["subject"],
        _render(
            tpl["html"],
            name=name,
            event_line_html=event_line_html,
            expiration_line_html=expiration_line_html,
        ),
        _render(
            tpl["text"],
            name=name,
            event_line=event_line,
            expiration_line=expiration_line,
        ),
    )


# ── dispatch ────────────────────────────────────────────────────────────────


async def send_welcome(settings: Settings, user: User) -> bool:
    subject, html, text = build_welcome(user)
    return await email_gateway.send_email(
        settings, to=user.email, subject=subject, html=html, text=text
    )


async def send_purchase_receipt(
    settings: Settings,
    user: User,
    *,
    event_type: str,
    store: str | None = None,
    product_id: str | None = None,
    expiration: str | None = None,
) -> bool:
    subject, html, text = build_receipt(
        user,
        event_type=event_type,
        store=store,
        product_id=product_id,
        expiration=expiration,
    )
    return await email_gateway.send_email(
        settings, to=user.email, subject=subject, html=html, text=text
    )
