"""Time-of-day greeting for the empty chat."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.orm import User


def greeting(user: User, tz: ZoneInfo) -> str:
    hour = datetime.now(tz).hour
    name = (user.name or "").strip().split()[0] if user.name else None
    if 5 <= hour < 12:
        phrase = "Good morning"
    elif 12 <= hour < 17:
        phrase = "Good afternoon"
    elif 17 <= hour < 22:
        phrase = "Good evening"
    else:
        phrase = "Hey there"
    if name:
        return f"{phrase}, {name}"
    return phrase
