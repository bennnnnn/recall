"""Transactional email content + dispatch (welcome, purchase receipts, to-do reminders).

Every email is in the user's language (``user.locale``): each app language has its own copy
(``email_copy``), English only for a locale the app does not offer. No word of an email is
RevenueCat's or the code's own (an event name, a store id, a timestamp). All dispatch goes
through ``email_gateway.deliver_email``; a welcome or receipt a later try may deliver is
retried by its job (``require_sent``).
"""

from __future__ import annotations

import html as html_lib
from datetime import datetime
from typing import Any

from app.core.config import Settings
from app.gateways import email_gateway
from app.models.orm import User
from app.modules.notifications.email_copy import (
    GREETINGS,
    RECEIPT_LINES,
    STORE_NAMES,
    TEMPLATES,
)
from app.services import locale as locale_service

# Locale codes supported by the mobile app (mirrors services/locale.py).
_SUPPORTED_LOCALES = frozenset(locale_service.LOCALE_NAMES.keys())


def _locale_for(user: User) -> str:
    code = locale_service.normalize_locale_code(user.locale)
    return code if code in _SUPPORTED_LOCALES else "en"


def _greeting(user: User, locale: str, *, html: bool) -> str:
    """The email's opening line in ``locale``: by name, or without one when there is none."""
    name = (user.name or "").strip()
    bundle = GREETINGS.get(locale, GREETINGS["en"])
    if not name:
        return _esc(bundle["unnamed"]) if html else bundle["unnamed"]
    return bundle["named"].format(name=_esc(name) if html else name)


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

    Every value going into the HTML template is escaped: name, title, content and body
    are user-entered (a to-do's text, a display name) and the receipt's store and date come
    from RevenueCat webhooks, so a to-do titled ``<img src=x onerror=...>`` would otherwise
    be live markup in the recipient's mail client. Not for the ``text`` variant: plain text
    needs no escaping, and ``&amp;`` would only be noise.
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
    return (
        tpl["subject"],
        _render(tpl["html"], greeting=_greeting(user, locale, html=True)),
        _render(tpl["text"], greeting=_greeting(user, locale, html=False)),
    )


def receipt_lines(
    locale: str, *, event_type: str, store: str | None, expiration: str | None
) -> tuple[list[str], str | None]:
    """The receipt's lines in ``locale``: what happened to the plan and the store it was
    bought through, then the day it renews (read in UTC), or None. A store or a date it
    cannot name is left out."""
    copy = RECEIPT_LINES.get(locale, RECEIPT_LINES["en"])
    lines = [copy.get(event_type, copy["other"])]
    store_name = STORE_NAMES.get((store or "").strip().lower())
    if store_name:
        lines.append(copy["store"].format(store=store_name))
    day = _day(expiration)
    return lines, None if day is None else copy["renews"].format(date=day)


def _day(instant: str | None) -> str | None:
    """``2026-08-01T00:00:00+00:00`` as the date ``2026-08-01``; None when it is no time."""
    if not instant:
        return None
    try:
        return datetime.fromisoformat(instant).date().isoformat()
    except ValueError:
        return None


def build_receipt(
    user: User,
    *,
    event_type: str,
    store: str | None = None,
    expiration: str | None = None,
) -> tuple[str, str, str]:
    """Return (subject, html, text) for a purchase/renewal receipt."""
    locale = _locale_for(user)
    tpl = _template("receipt", locale)
    lines, renews = receipt_lines(locale, event_type=event_type, store=store, expiration=expiration)
    return (
        tpl["subject"],
        _render(
            tpl["html"],
            greeting=_greeting(user, locale, html=True),
            event_line_html="".join(f"{_esc(line)}<br/>" for line in lines),
            expiration_line_html=f"{_esc(renews)}<br/>" if renews else "",
        ),
        _render(
            tpl["text"],
            greeting=_greeting(user, locale, html=False),
            event_line="".join(f"{line}\n" for line in lines),
            expiration_line=f"{renews}\n" if renews else "",
        ),
    )


def build_todo_reminder(user: User, *, title: str, content: str) -> tuple[str, str, str]:
    locale = _locale_for(user)
    tpl = _template("todo_reminder", locale)
    return (
        _render(tpl["subject"], title=title, content=_strip_header_chars(content)),
        _render(
            tpl["html"],
            greeting=_greeting(user, locale, html=True),
            title=_esc(title),
            content=_esc(content),
        ),
        _render(
            tpl["text"],
            greeting=_greeting(user, locale, html=False),
            title=title,
            content=content,
        ),
    )


# ── dispatch ────────────────────────────────────────────────────────────────


class EmailNotSentError(Exception):
    """A welcome or receipt the provider did not take, and may on a later try (a timeout,
    a 429, a 5xx, the account's key or sender): the job raises it so the worker retries."""


def require_sent(result: email_gateway.EmailResult, kind: str) -> None:
    """Raise for a send a later try may deliver. A message the provider refused for good
    (a bad address) and one never attempted (email off) are not tried again."""
    if result.outcome is email_gateway.EmailOutcome.RETRY:
        raise EmailNotSentError(f"transactional_email {kind} not sent; retrying")


async def send_welcome(settings: Settings, user: User) -> email_gateway.EmailResult:
    subject, html, text = build_welcome(user)
    return await email_gateway.deliver_email(
        settings,
        to=user.email,
        subject=subject,
        html=html,
        text=text,
        # A retry after a timeout the provider had already taken mails nothing twice.
        idempotency_key=f"welcome:{user.id}",
    )


async def send_purchase_receipt(
    settings: Settings,
    user: User,
    *,
    event_type: str,
    store: str | None = None,
    product_id: str | None = None,
    expiration: str | None = None,
) -> email_gateway.EmailResult:
    """The receipt; ``product_id`` keys its send (one per purchase), never its words."""
    subject, html, text = build_receipt(
        user, event_type=event_type, store=store, expiration=expiration
    )
    return await email_gateway.deliver_email(
        settings,
        to=user.email,
        subject=subject,
        html=html,
        text=text,
        idempotency_key=f"receipt:{user.id}:{event_type}:{product_id or ''}:{expiration or ''}",
    )


async def send_todo_reminder(
    settings: Settings, user: User, *, title: str, content: str, idempotency_key: str
) -> email_gateway.EmailResult:
    """One reminder email; what became of it, so the cycle can wait or give up."""
    subject, html, text = build_todo_reminder(user, title=title, content=content)
    return await email_gateway.deliver_email(
        settings,
        to=user.email,
        subject=subject,
        html=html,
        text=text,
        idempotency_key=idempotency_key,
    )
