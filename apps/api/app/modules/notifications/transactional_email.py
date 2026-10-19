"""Transactional email content + dispatch (welcome, purchase receipts).

Templates are locale-aware via ``user.locale``. English is the source and the
fallback for any locale without a dedicated translation; the structure makes
adding more locales a data-only change. All dispatch goes through
``email_gateway.send_email`` and is best-effort.
"""

from __future__ import annotations

import html as html_lib
import logging
from typing import Any

from app.core.config import Settings
from app.gateways import email_gateway
from app.models.orm import User
from app.modules.notifications.email_copy import TEMPLATES
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


def _template(kind: str, locale: str) -> dict[str, str]:
    bundle = TEMPLATES.get(kind, {})
    return bundle.get(locale) or bundle["en"]


def _render(template: str, **kwargs: Any) -> str:
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def _esc(value: object) -> str:
    """HTML-escape a value bound for an `html` template variant.

    BUG FIX (was silent): _render() used to interpolate values into the html
    template exactly like the text one — no escaping. name/title/content/body
    are all user-entered (todo content, display
    name) and event_type/store/product_id come from RevenueCat webhook data.
    Unescaped, a todo titled e.g. `<img src=x onerror=...>` renders as live
    markup in the recipient's HTML email client. Never call this on values
    going into the `text` variant — plain text doesn't need escaping and
    `&amp;` etc. would just be visual noise.
    """
    return html_lib.escape(str(value))


def _strip_header_chars(value: str) -> str:
    """Defense-in-depth: user content must never reach a Subject line with
    embedded CR/LF. Resend's API takes `subject` as a JSON field rather than
    raw SMTP header text, so classic header injection isn't known-exploitable
    through this specific provider, but this is cheap and provider-independent.
    """
    return value.replace("\r", " ").replace("\n", " ")


def build_welcome(user: User) -> tuple[str, str, str]:
    """Return (subject, html, text) for the welcome email."""
    locale = _locale_for(user)
    tpl = _template("welcome", locale)
    name = _display_name(user)
    return (
        tpl["subject"],
        _render(tpl["html"], name=_esc(name)),
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

    # Built independently from event_line/expiration_line (not derived via
    # str.replace) so each field can be escaped before it's embedded — the
    # text variant must stay unescaped, so the two can't share one fragment.
    event_line_html = f"Event: {_esc(event_type)}<br/>"
    if store:
        event_line_html += f"Store: {_esc(store)}<br/>"
    if product_id:
        event_line_html += f"Product: {_esc(product_id)}<br/>"
    expiration_line_html = f"Renews: {_esc(expiration)}<br/>" if expiration else ""

    return (
        tpl["subject"],
        _render(
            tpl["html"],
            name=_esc(name),
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


def build_todo_reminder(user: User, *, title: str, content: str) -> tuple[str, str, str]:
    locale = _locale_for(user)
    tpl = _template("todo_reminder", locale)
    name = _display_name(user)
    return (
        _render(tpl["subject"], title=title, content=_strip_header_chars(content)),
        _render(tpl["html"], name=_esc(name), title=_esc(title), content=_esc(content)),
        _render(tpl["text"], name=name, title=title, content=content),
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


async def send_todo_reminder(settings: Settings, user: User, *, title: str, content: str) -> bool:
    subject, html, text = build_todo_reminder(user, title=title, content=content)
    return await email_gateway.send_email(
        settings, to=user.email, subject=subject, html=html, text=text
    )
