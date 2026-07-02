"""Expo Push API gateway."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


@dataclass
class PushSendResult:
    """Per-message Expo ticket outcomes (parallel to the input list)."""

    invalid_tokens: list[str]
    delivered: list[bool]


async def send_push_messages(messages: list[dict[str, Any]]) -> PushSendResult:
    """Send push messages via Expo.

    Returns invalid tokens to prune and a delivered flag per input message.
    On a transport/API failure, nothing is marked delivered so the caller can retry.
    """
    if not messages:
        return PushSendResult(invalid_tokens=[], delivered=[])

    invalid: list[str] = []
    delivered = [False] * len(messages)
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
                    if ticket.get("status") == "ok":
                        delivered[i] = True
                        continue
                    if ticket.get("status") == "error":
                        details = ticket.get("details", {})
                        err = details.get("error", "")
                        if err in ("DeviceNotRegistered", "InvalidCredentials"):
                            token = messages[i].get("to", "")
                            if token:
                                invalid.append(token)
            except Exception:
                logger.debug("Expo response parse failed", exc_info=True)
    except Exception:
        logger.exception("Expo push send failed count=%s", len(messages))
    return PushSendResult(invalid_tokens=invalid, delivered=delivered)
