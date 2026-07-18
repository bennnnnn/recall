"""Time-of-day greeting and planning starter chips."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from app.models.orm import User
from app.models.schemas import HomeStarter
from app.services.home.util import (
    CALENDAR_TODAY_END_HOUR,
    MORNING_START_HOUR,
    REFLECT_START_HOUR,
    local_hour_for_tz,
)


def greeting(user: User, tz: ZoneInfo) -> str:
    hour = local_hour_for_tz(tz)
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


def welcome_starters() -> list[HomeStarter]:
    """First-session / empty-account chips — no assumed day history."""
    return [
        HomeStarter(
            text="Help me think",
            prompt="I want to talk something through — ask me a good opening question.",
            kind="general",
        ),
        HomeStarter(
            text="What can you do?",
            prompt="What can you help me with? Give a few concrete examples.",
            kind="general",
        ),
    ]


def time_starters(user: User, tz: ZoneInfo) -> list[HomeStarter]:
    hour = local_hour_for_tz(tz)
    if MORNING_START_HOUR <= hour < CALENDAR_TODAY_END_HOUR:
        candidates = [
            HomeStarter(
                text="Plan my day",
                prompt="Help me plan my day based on what you know about me.",
                kind="time",
            ),
            HomeStarter(
                text="What's worth focusing on?",
                prompt="What should I focus on today?",
                kind="time",
            ),
        ]
    elif CALENDAR_TODAY_END_HOUR <= hour < REFLECT_START_HOUR:
        candidates = [
            HomeStarter(
                text="What are you working on?",
                prompt="What am I trying to get done today?",
                kind="time",
            ),
            HomeStarter(
                text="What's left today?",
                prompt="What's still open for me to finish today?",
                kind="time",
            ),
        ]
    elif REFLECT_START_HOUR <= hour < 22:
        candidates = [
            HomeStarter(
                text="How did today go?",
                prompt="How did my day go? Help me reflect and wrap up loose ends.",
                kind="time",
            ),
            HomeStarter(
                text="Anything left tonight?",
                prompt="What's still open for me to finish tonight?",
                kind="time",
            ),
        ]
    else:
        candidates = [
            HomeStarter(
                text="Still up?",
                prompt="I'm still up — what should I tackle or wind down?",
                kind="time",
            ),
            HomeStarter(
                text="Quick thought",
                prompt="I have a quick thought I want to talk through.",
                kind="time",
            ),
        ]
    return candidates[:2]
