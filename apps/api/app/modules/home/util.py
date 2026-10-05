"""Shared home-screen helpers (timezone and cache seed)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.orm import User
from app.services import time_context as time_context_service


def resolve_home_tz(user: User, client_timezone: str | None = None) -> ZoneInfo:
    return time_context_service.resolve_timezone(
        time_context_service.effective_timezone(user.timezone, client_timezone)
    )


def local_hour_for_tz(tz: ZoneInfo) -> int:
    return datetime.now(tz).hour


def day_seed(user: User, tz: ZoneInfo) -> int:
    day = datetime.now(tz).strftime("%Y-%m-%d")
    digest = hashlib.sha256(f"{user.id}:{day}".encode()).hexdigest()
    return int(digest[:8], 16)
