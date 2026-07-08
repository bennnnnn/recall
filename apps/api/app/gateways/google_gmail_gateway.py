"""Google Gmail OAuth + message fetch (server-side only)."""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

from app.core.config import Settings
from app.gateways.google_calendar_gateway import GoogleCalendarError, exchange_server_auth_code
from app.gateways.http_client import get_pooled_client

logger = logging.getLogger(__name__)

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
TOKEN_URL = "https://oauth2.googleapis.com/token"
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
    payload = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        client = get_pooled_client(DEFAULT_TIMEOUT)
        response = await client.post(TOKEN_URL, data=payload)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.exception("Gmail token refresh failed")
        raise GoogleGmailError("Could not refresh Gmail access.") from exc

    token = str(data.get("access_token") or "").strip()
    if not token:
        raise GoogleGmailError("Gmail access token missing.")
    return token


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


def _walk_parts(payload: dict[str, Any]) -> tuple[str, str | None]:
    """Return (plain text body, ics attachment content if any)."""
    mime = str(payload.get("mimeType") or "")
    body_data = payload.get("body") or {}
    data = body_data.get("data")
    text = ""
    ics: str | None = None

    if mime == "text/plain" and data:
        text = _decode_body(str(data))
    elif mime == "text/calendar" and data:
        ics = _decode_body(str(data))
    elif mime.startswith("multipart/"):
        for part in payload.get("parts") or []:
            part_text, part_ics = _walk_parts(part)
            if part_text and not text:
                text = part_text
            if part_ics and not ics:
                ics = part_ics
            filename = str(part.get("filename") or "").lower()
            if filename.endswith(".ics"):
                part_body = part.get("body") or {}
                if part_body.get("data"):
                    ics = _decode_body(str(part_body["data"]))

    return text, ics


def parse_ics_event(ics_content: str) -> tuple[str | None, datetime | None]:
    """Best-effort parse SUMMARY and DTSTART from ICS content."""
    summary_match = re.search(r"SUMMARY(?:;[^:]*)?:(.+)", ics_content, re.IGNORECASE)
    title = summary_match.group(1).strip() if summary_match else None
    if title:
        title = title.replace("\\n", " ").replace("\\,", ",")

    dtstart_match = re.search(
        r"DTSTART(?:;[^:]*)?:(\d{8}T?\d{0,6}Z?)",
        ics_content,
        re.IGNORECASE,
    )
    due_at: datetime | None = None
    if dtstart_match:
        raw = dtstart_match.group(1).strip()
        try:
            if "T" in raw:
                if raw.endswith("Z"):
                    due_at = datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
                else:
                    due_at = datetime.strptime(raw[:15], "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
            else:
                due_at = datetime.strptime(raw[:8], "%Y%m%d").replace(tzinfo=UTC)
        except ValueError:
            due_at = None

    return title, due_at


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

        fetched = await asyncio.gather(*(_bounded(ref) for ref in message_refs[:max_messages]))
        messages.extend(msg for msg in fetched if msg is not None)
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
        return await exchange_server_auth_code(settings, code)
    except GoogleCalendarError as exc:
        raise GoogleGmailError(str(exc)) from exc
