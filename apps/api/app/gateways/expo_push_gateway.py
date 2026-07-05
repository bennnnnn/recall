"""Expo Push API gateway."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPTS_URL = "https://exp.host/--/api/v2/push/getReceipts"
MAX_RECEIPTS_PER_REQUEST = 100
_INVALID_TOKEN_ERRORS = frozenset({"DeviceNotRegistered", "InvalidCredentials"})


@dataclass
class PushSendResult:
    """Per-message Expo ticket outcomes (parallel to the input list)."""

    invalid_tokens: list[str]
    delivered: list[bool]
    receipt_tickets: list[tuple[str, str]] = field(default_factory=list)


def _invalid_token_from_error(details: object) -> str | None:
    if not isinstance(details, dict):
        return None
    err = details.get("error", "")
    if err not in _INVALID_TOKEN_ERRORS:
        return None
    return err


async def fetch_push_receipts(ticket_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Return receipt payloads keyed by Expo ticket id."""
    if not ticket_ids:
        return {}

    receipts: dict[str, dict[str, Any]] = {}
    async with httpx.AsyncClient(timeout=15.0) as client:
        for offset in range(0, len(ticket_ids), MAX_RECEIPTS_PER_REQUEST):
            chunk = ticket_ids[offset : offset + MAX_RECEIPTS_PER_REQUEST]
            try:
                response = await client.post(
                    EXPO_RECEIPTS_URL,
                    json={"ids": chunk},
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
                response.raise_for_status()
                body = response.json()
            except Exception:
                logger.exception("Expo push receipt fetch failed count=%s", len(chunk))
                continue
            data = body.get("data")
            if not isinstance(data, dict):
                continue
            for ticket_id, receipt in data.items():
                if isinstance(receipt, dict):
                    receipts[str(ticket_id)] = receipt
    return receipts


def receipt_indicates_invalid_token(receipt: dict[str, Any]) -> bool:
    if receipt.get("status") != "error":
        return False
    return _invalid_token_from_error(receipt.get("details", {})) is not None


async def send_push_messages(messages: list[dict[str, Any]]) -> PushSendResult:
    """Send push messages via Expo.

    Marks a message delivered when Expo accepts the ticket. Receipt polling for
    stale-token cleanup is deferred — see push_notifications.poll_deferred_receipts.
    On a transport/API failure, nothing is marked delivered so the caller can retry.
    """
    if not messages:
        return PushSendResult(invalid_tokens=[], delivered=[])

    invalid: list[str] = []
    delivered = [False] * len(messages)
    receipt_tickets: list[tuple[str, str]] = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                EXPO_PUSH_URL,
                json=messages,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            response.raise_for_status()
            try:
                body = response.json()
                tickets = body.get("data", [])
                for i, ticket in enumerate(tickets):
                    if i >= len(messages):
                        break
                    if not isinstance(ticket, dict):
                        continue
                    token = str(messages[i].get("to", "") or "")
                    if ticket.get("status") == "ok":
                        ticket_id = ticket.get("id")
                        if isinstance(ticket_id, str) and ticket_id:
                            delivered[i] = True
                            if token:
                                receipt_tickets.append((ticket_id, token))
                        continue
                    if ticket.get("status") == "error":
                        details = ticket.get("details", {})
                        err = _invalid_token_from_error(details)
                        if err and token:
                            invalid.append(token)
            except Exception:
                logger.debug("Expo response parse failed", exc_info=True)
    except Exception:
        logger.exception("Expo push send failed count=%s", len(messages))
        return PushSendResult(invalid_tokens=invalid, delivered=delivered)

    return PushSendResult(
        invalid_tokens=invalid,
        delivered=delivered,
        receipt_tickets=receipt_tickets,
    )
