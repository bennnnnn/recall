"""Expo Push API gateway."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def send_push_messages(messages: list[dict[str, Any]]) -> None:
    if not messages:
        return
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                EXPO_PUSH_URL,
                json=messages,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            response.raise_for_status()
    except Exception:
        logger.exception("Expo push send failed count=%s", len(messages))
