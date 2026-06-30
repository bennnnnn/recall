"""Expo Push API gateway."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def send_push_messages(messages: list[dict[str, Any]]) -> list[str]:
    """Send push messages via Expo. Returns tokens that should be pruned
    (DeviceNotRegistered / invalid)."""
    if not messages:
        return []
    failed: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                EXPO_PUSH_URL,
                json=messages,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            response.raise_for_status()
            # Parse per-ticket results to find invalid tokens to prune.
            try:
                body = response.json()
                tickets = body.get("data", [])
                for i, ticket in enumerate(tickets):
                    if ticket.get("status") == "error":
                        details = ticket.get("details", {})
                        err = details.get("error", "")
                        if err in ("DeviceNotRegistered", "InvalidCredentials"):
                            token = messages[i].get("to", "") if i < len(messages) else ""
                            if token:
                                failed.append(token)
            except Exception:
                logger.debug("Expo response parse failed", exc_info=True)
    except Exception:
        logger.exception("Expo push send failed count=%s", len(messages))
    return failed
