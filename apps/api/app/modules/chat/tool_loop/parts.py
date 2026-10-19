"""Which of the turn's requests the tool loop takes, and which of those need a search.

The gates used to read the whole message as one request, so one part could cancel
another: "remind me to buy milk and what's the weather in Nairobi?" never searched
(a reminder turn skips search), nor did "teach me dictionaries, and what is the
price of bitcoin?" (a request to make something asks nothing to look up), and a
verified "solve 2x + 5 = 17" skipped the loop the weather half needed. Each gate now
asks per part of the turn's plan (``turn_prep.intents``). A one-part message (nearly
every turn) is the whole message, exactly as before.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from app.core.config import Settings
from app.modules.chat.turn_plan import HANDLED_KINDS, TurnPlan


def turn_plan(text: str, settings: Settings | None = None) -> TurnPlan:
    from app.modules.chat.turn_prep.intents import plan_turn

    return plan_turn(text, chemistry_enabled=settings is None or settings.chemistry_enabled)


def open_parts(
    text: str, *, has_verified_math: bool = False, settings: Settings | None = None
) -> list[str]:
    """The requests still open for a tool, each in the user's own words.

    One part is the whole message, or nothing once its solve is verified. On a
    multi-part plan the verified solve answers only its maths part, and the
    settings, picture and photo parts belong to their own paths, never the loop's.
    """
    plan = turn_plan(text, settings)
    if not plan.multi:
        return [] if has_verified_math else [text]
    done = {*HANDLED_KINDS, "solve"} if has_verified_math else set(HANDLED_KINDS)
    return [part.text for part in plan.parts if part.kind not in done]


def live_parts(parts: Sequence[str]) -> list[str]:
    """The parts the sync search gate says need live results."""
    from app.modules.web_search.detection import needs_web_search

    return [part for part in parts if needs_web_search(part)]


async def classified_live_parts(
    parts: Sequence[str],
    settings: Settings,
    *,
    prior_user_messages: list[str] | None,
    prior_assistant: str | None,
) -> list[str]:
    """The parts the search gate (classifier included) says need live results.

    One part keeps the chat's earlier turns, as before. Parts of one message are
    asked side by side and without them: each is a request of its own, and a short
    "tell me a joke" after a weather question is not that question's follow-up.
    """
    from app.modules.web_search.detection import should_web_search

    if len(parts) == 1:
        found = await should_web_search(
            parts[0],
            settings,
            prior_user_messages=prior_user_messages,
            prior_assistant=prior_assistant,
        )
        return list(parts) if found else []
    verdicts = await asyncio.gather(*(should_web_search(part, settings) for part in parts))
    return [part for part, needed in zip(parts, verdicts, strict=True) if needed]
