"""Google Gmail OAuth + message fetch (server-side only)."""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

from app.core.config import Settings
from app.gateways import google_oauth
from app.gateways.http_client import get_pooled_client

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
DEFAULT_TIMEOUT = 15.0


class GoogleGmailError(Exception):
    pass


@dataclass(frozen=True)
class GmailMessage:
    id: str
    subject: str
    snippet: str
    body_text: str
    received_at: datetime | None
    ics_content: str | None = None
    from_address: str = ""
    label_ids: tuple[str, ...] = ()


def is_configured(settings: Settings) -> bool:
    return bool(
        settings.gmail_enabled
        and settings.google_client_id.strip()
        and settings.google_client_secret.strip()
    )


async def _access_token(settings: Settings, refresh_token: str) -> str:
    try:
        return await google_oauth.refresh_access_token(settings, refresh_token)
    except google_oauth.GoogleOAuthError as exc:
        raise GoogleGmailError("Could not refresh Gmail access.") from exc


def _decode_body(data: str) -> str:
    try:
        raw = base64.urlsafe_b64decode(data + "==")
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_header(headers: list[dict[str, str]], name: str) -> str:
    lower = name.lower()
    for header in headers:
        if str(header.get("name", "")).lower() == lower:
            return str(header.get("value") or "").strip()
    return ""


# Crafted MIME trees can nest forever; walk iteratively with hard caps.
_MAX_MIME_DEPTH = 32
_MAX_MIME_PARTS = 200


def _walk_parts(payload: dict[str, Any]) -> tuple[str, str | None]:
    """Return (plain text body, ics attachment content if any)."""
    text = ""
    ics: str | None = None
    stack: list[tuple[dict[str, Any], int]] = [(payload, 0)]
    seen = 0

    while stack:
        node, depth = stack.pop()
        seen += 1
        if seen > _MAX_MIME_PARTS:
            break

        mime = str(node.get("mimeType") or "")
        body_data = node.get("body") or {}
        data = body_data.get("data")
        filename = str(node.get("filename") or "").lower()

        if mime == "text/plain" and data and not text:
            text = _decode_body(str(data))
        elif mime == "text/calendar" and data and not ics:
            ics = _decode_body(str(data))
        elif filename.endswith(".ics") and data and not ics:
            ics = _decode_body(str(data))

        if mime.startswith("multipart/") and depth < _MAX_MIME_DEPTH:
            children = node.get("parts") or []
            for child in reversed(children):
                if isinstance(child, dict):
                    stack.append((child, depth + 1))

    return text, ics


logger = logging.getLogger(__name__)


async def list_recent_messages(
    settings: Settings,
    refresh_token: str,
    *,
    days: int = 7,
    max_messages: int = 30,
) -> list[GmailMessage]:
    if not is_configured(settings):
        raise GoogleGmailError("Gmail is not configured on the server.")

    access = await _access_token(settings, refresh_token)
    after = datetime.now(UTC) - timedelta(days=days)
    after_epoch = int(after.timestamp())
    query = f"in:inbox after:{after_epoch}"

    headers = {"Authorization": f"Bearer {access}"}
    messages: list[GmailMessage] = []

    try:
        client = get_pooled_client(DEFAULT_TIMEOUT)
        list_resp = await client.get(
            GMAIL_MESSAGES_URL,
            params={"q": query, "maxResults": max_messages},
            headers=headers,
        )
        if list_resp.status_code == 403:
            raise GoogleGmailError(
                "Gmail access denied. In Google Cloud Console, enable the Gmail API "
                "for this project, then disconnect and reconnect Gmail in Settings."
            )
        if list_resp.status_code == 401:
            raise GoogleGmailError(
                "Gmail authorization expired. Disconnect and reconnect Gmail in Settings."
            )
        list_resp.raise_for_status()
        list_data = list_resp.json()
        message_refs = list_data.get("messages") or []

        async def _fetch_message(ref: dict[str, object]) -> GmailMessage | None:
            msg_id = str(ref.get("id") or "")
            if not msg_id:
                return None
            detail_resp = await client.get(
                f"{GMAIL_MESSAGES_URL}/{msg_id}",
                params={"format": "full"},
                headers=headers,
            )
            detail_resp.raise_for_status()
            detail = detail_resp.json()
            payload = detail.get("payload") or {}
            hdrs = payload.get("headers") or []
            subject = _extract_header(hdrs, "Subject")
            from_address = _extract_header(hdrs, "From")
            snippet = str(detail.get("snippet") or "")
            label_ids = tuple(str(label) for label in (detail.get("labelIds") or []))
            date_hdr = _extract_header(hdrs, "Date")
            received_at: datetime | None = None
            if date_hdr:
                try:
                    received_at = parsedate_to_datetime(date_hdr)
                    if received_at.tzinfo is None:
                        received_at = received_at.replace(tzinfo=UTC)
                except Exception:
                    received_at = None

            body_text, ics_content = _walk_parts(payload)
            return GmailMessage(
                id=msg_id,
                subject=subject,
                snippet=snippet,
                body_text=body_text or snippet,
                received_at=received_at,
                ics_content=ics_content,
                from_address=from_address,
                label_ids=label_ids,
            )

        sem = asyncio.Semaphore(8)

        async def _bounded(ref: dict[str, object]) -> GmailMessage | None:
            async with sem:
                return await _fetch_message(ref)

        # BUG FIX (was a stuck-sync bug): this used to gather without
        # return_exceptions, so one failing message detail fetch (a
        # transient API hiccup, rate limit, or malformed payload) aborted
        # the whole batch and discarded every other successfully-fetched
        # message. Worse, the exception propagated out of sync_gmail_for_user
        # before last_sync_at was updated, so the same message would be
        # re-fetched — and could re-fail — on every subsequent periodic
        # cycle, silently stalling that user's sync indefinitely. Isolate
        # per-message failures the same way list_upcoming_events already
        # does for per-calendar failures.
        fetched = await asyncio.gather(
            *(_bounded(ref) for ref in message_refs[:max_messages]),
            return_exceptions=True,
        )
        failed = 0
        for item in fetched:
            if isinstance(item, BaseException):
                failed += 1
                logger.warning("Skipping Gmail message fetch: %s", item)
                continue
            if item is not None:
                messages.append(item)
        if failed:
            logger.info("Gmail message fetch: %s of %s failed", failed, len(fetched))
    except GoogleGmailError:
        raise
    except Exception as exc:
        logger.exception("Gmail list messages failed")
        raise GoogleGmailError("Could not fetch Gmail messages.") from exc

    return messages


async def exchange_gmail_auth_code(settings: Settings, code: str) -> dict[str, Any]:
    if not is_configured(settings):
        raise GoogleGmailError("Gmail is not configured on the server.")
    try:
        return await google_oauth.exchange_auth_code(settings, code)
    except google_oauth.GoogleOAuthError as exc:
        raise GoogleGmailError("Could not connect Gmail.") from exc
