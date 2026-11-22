"""A reminder request read from the chat by a model, in any wording, over any number of lines.

The word rules (``spoken_add``, ``spoken_clauses``, ``card_retime``) read a request in the
shapes they know. In a live QA round (2026-11-22, an ordinary user on the phone's send path)
16 of 30 reminder requests got no card: the task came in one line and its time in the next
("tmrw at 5 lol" after "When should I remind you?"), a time sat inside a long greeting, an
hour was "an hour before" a dinner. The reply's model asked again and again, or said the
reminder was set with nothing saved. When the turn's read says the message asks for a
reminder (``chat.turn_decision``: ``reminder``) and the word rules made no card, a model
reads the chat and writes the request down as it stands now: the task, the day and the time
as the user said them, each with the user's own words (``ReminderReading``). The server
holds every value to those words and works the time out in the user's zone
(``read_check``); the model never computes a date or an hour that is saved.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.config import Settings
from app.models.routing_lanes import ROUTING

logger = logging.getLogger(__name__)

Request = Literal["add", "status", "none"]
Half = Literal["am", "pm", ""]
Repeat = Literal["daily", "weekdays", "weekly", "monthly", ""]

_MAX_TOKENS = 300
# The chat the read sees: the last messages, a user line whole up to its cap, a reply's
# start (a card in it is shown as the app's own line, never its JSON).
_MESSAGES = 8
_USER_CHARS = 500
_REPLY_CHARS = 400

PROMPT = (
    "You read a chat for an app that keeps the user's reminders. Today is {today}. Read the "
    "user's last message against the chat before it and write down, as JSON, the reminder "
    "request as it stands now.\n"
    "\n"
    "request: add when the last message asks to be reminded of something, gives the task, "
    "day or time of a reminder the chat is setting up, or changes the time of a reminder "
    "card the assistant offered that the user has not tapped; status when it asks whether "
    "a reminder they asked for was set or saved; none for anything else (asking to be told "
    "or taught something, a memory, how reminders work, a plan with no reminder asked).\n"
    "Then, for add and status, the reminder from anywhere in the chat, the latest wording "
    "when the user changed it. Every quote is the user's own words, copied exactly from one "
    "of their messages; leave a value and its quote empty when no user line states it, and "
    "never fill one in:\n"
    "- task: what to remind them of, short, in their words (call my sister Margaret), "
    "naming the thing itself, never it or that: for 'write it down' about a dream, write "
    "down my dream; "
    "task_quote: the words that say it\n"
    "- day: the day as they said it (tmrw, friday, next monday, dec 3, tonight); date: that "
    "day as YYYY-MM-DD; day_quote\n"
    "- time: the clock as they said it (5, 5pm, 17:30, noon, morning, this afternoon); "
    "time_quote\n"
    "- half: am or pm only when their words say which half of the day that clock is "
    "(pm, in the afternoon, after dinner, before work); half_quote\n"
    "- in_minutes: a time from now (in 2 hours is 120); in_quote\n"
    "- before_minutes: how long before that time to remind them (an hour before is 60); "
    "before_quote\n"
    "- repeat: daily, weekdays, weekly or monthly when they asked for a repeat; "
    "repeat_quote\n"
    "\n"
    'Example: "User: can u remind me to grab an umbrella tmrw at 5?" "Assistant: When '
    'should I remind you?" "User (last): tmrw at 5 lol" -> {{"request": "add", "task": '
    '"grab an umbrella", "task_quote": "grab an umbrella", "day": "tmrw", "date": '
    '"2026-11-23", "day_quote": "tmrw", "time": "5", "time_quote": "at 5", "half": "", '
    '"half_quote": "", "in_minutes": null, "in_quote": "", "before_minutes": null, '
    '"before_quote": "", "repeat": "", "repeat_quote": ""}}'
)


def _choice(value: Any, choices: tuple[str, ...], default: str) -> str:
    text = str(value).strip().lower() if value is not None else ""
    return text if text in choices else default


class ReminderReading(BaseModel):
    """The reminder request the chat makes now, as a model reads it: a candidate only."""

    request: Request = "none"
    task: str = Field(default="", max_length=200)
    task_quote: str = Field(default="", max_length=300)
    day: str = Field(default="", max_length=60)
    date: str = Field(default="", max_length=20)
    day_quote: str = Field(default="", max_length=120)
    time: str = Field(default="", max_length=40)
    time_quote: str = Field(default="", max_length=120)
    half: Half = ""
    half_quote: str = Field(default="", max_length=120)
    in_minutes: int | None = Field(default=None, ge=1, le=527_040)
    in_quote: str = Field(default="", max_length=120)
    before_minutes: int | None = Field(default=None, ge=1, le=10_080)
    before_quote: str = Field(default="", max_length=120)
    repeat: Repeat = ""
    repeat_quote: str = Field(default="", max_length=120)

    @field_validator("request", mode="before")
    @classmethod
    def _request(cls, value: Any) -> str:
        return _choice(value, ("add", "status", "none"), "none")

    @field_validator("half", mode="before")
    @classmethod
    def _half(cls, value: Any) -> str:
        return _choice(value, ("am", "pm"), "")

    @field_validator("repeat", mode="before")
    @classmethod
    def _repeat(cls, value: Any) -> str:
        return _choice(value, ("daily", "weekdays", "weekly", "monthly"), "")

    @field_validator(
        "task",
        "task_quote",
        "day",
        "date",
        "day_quote",
        "time",
        "time_quote",
        "half_quote",
        "in_quote",
        "before_quote",
        "repeat_quote",
        mode="before",
    )
    @classmethod
    def _text(cls, value: Any) -> str:
        return "" if value is None else str(value).strip()

    @field_validator("in_minutes", "before_minutes", mode="before")
    @classmethod
    def _minutes(cls, value: Any) -> int | None:
        """An odd count (0, "", a word) is no value, not a failed read."""
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            return None
        return minutes if minutes >= 1 else None


def chat_lines(conversation: list[tuple[str, str]], text: str) -> str:
    """The chat as the read sees it, the last message marked; a reply's card as the app's
    own line ("Card offered, not tapped, so nothing is saved — Set: …")."""
    from app.modules.todos.proposals import reminder_cards_as_text

    lines = []
    for role, content in conversation[-_MESSAGES:]:
        if role == "user":
            lines.append(f"User: {content[:_USER_CHARS]}")
        else:
            lines.append(f"Assistant: {reminder_cards_as_text(content)[:_REPLY_CHARS]}")
    lines.append(f"User (last): {text[:_USER_CHARS]}")
    return "\n".join(lines)


async def read_reminder_chat(
    settings: Settings,
    conversation: list[tuple[str, str]],
    text: str,
    *,
    now: datetime,
    model_alias: str | None = None,
) -> ReminderReading | None:
    """The model's reading of the chat's reminder request, or None when there is no read.
    ``now`` is the user's local time: the prompt names today so "tmrw" has a date."""
    from app.core.redis import get_redis_client
    from app.gateways.structured_completion import complete_structured
    from app.services import quota as quota_service

    try:
        if await quota_service.global_spend_exceeded(get_redis_client(), settings):
            return None
        today = now.strftime("%A, %Y-%m-%d, %H:%M")
        return await complete_structured(
            settings=settings,
            model_alias=model_alias or ROUTING.reminder_read,
            messages=[
                {"role": "system", "content": PROMPT.format(today=today)},
                {"role": "user", "content": chat_lines(conversation, text)},
            ],
            schema=ReminderReading,
            max_tokens=_MAX_TOKENS,
            timeout_seconds=settings.reminder_read_timeout_seconds,
            allow_fallback=False,
            quiet_timeout=True,
        )
    except Exception as exc:  # A read is a hint: any failure reads nothing.
        logger.info("reminder read failed (%s)", type(exc).__name__)
        return None
