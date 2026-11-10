"""What "it" is when a line asks to see it: a fast model reads the chat, not word rules.

"Draw it", "graph it", "show it" and "a picture of it" name nothing of their own. Live
(2026-11-09) "Draw it" after a triangle typed in pieces drew sin(x²)cos(x²) from six
messages back: the graph follow-up took the first plottable line it met. A word list that
tried to tell a new subject from a follow-up stopped at ordinary follow-ups instead ("what
is the domain?", "wow"). So one short structured call to a fast model reads the last six
exchanges, their user messages numbered, and names the one the user wants to see, or none.
The subject readers then look at that message only (``turn_reading.continued_problem``
completes it with the pieces that added to it): a curve, a shape or a physics scene is
drawn; data is the chart's; anything else is answered as before, with no older curve drawn
(a photo is looked up, or the model asks what to graph). A turn with no read (off, mocked,
failed or too slow) is answered as before: the graph follow-up reads the earlier lines back
to the first curve. Nothing here raises into a turn.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.core.config import Settings
from app.core.readings import keep_for_turn, kept_for_turn
from app.models.routing_lanes import ROUTING
from app.modules.turn_reading.continued_problem import problem_at
from app.modules.turn_reading.see_request import asks_to_see
from app.services.problem_followup import message_role_content
from app.services.subjects.registry import subject_adapter
from app.services.text_normalize import collapse_ws

logger = logging.getLogger(__name__)

# The last six exchanges.
_WINDOW = 12
_USER_CHARS = 300
_REPLY_CHARS = 200

_SYSTEM = (
    "The user's last message asks to see something from this conversation drawn, graphed "
    'or shown as a picture ("draw it", "graph it", "show it", "a picture of it"). Which '
    "numbered user message states that thing itself: the function or equation, the shape "
    "and its sizes, the problem, the data, or the person, place or object? Pick the message "
    'that states it, never a later question or remark about it ("what is the domain?", '
    '"wow"); when it was given in pieces, the message that started it. Answer null when '
    "they want the working, the steps or an explanation rather than a picture, when they "
    "only accept an offer, or when no message states it. Reply with JSON only: "
    '{"message": 3} or {"message": null}.'
)


class ReferentPick(BaseModel):
    message: int | None = None


@dataclass(frozen=True)
class Referent:
    """What the read found: the problem "it" is, whole, or None when it named none."""

    problem: str | None


def asks_for_a_referent(line: str) -> bool:
    """A request to see "it": "draw it", "graph this", "Plot", "show it", "a picture of it"."""
    return asks_to_see(line) or subject_adapter("math").followups.continues_alone(line)


def _exchanges(recent: Sequence[Any], line: str) -> list[tuple[str, str]]:
    """The chat before ``line``, oldest first: the turn's own saved line is left out."""
    pairs = [message_role_content(message) for message in recent]
    out = [(role, text) for role, text in pairs if role in {"user", "assistant"} and text]
    if out and out[-1][0] == "user" and collapse_ws(out[-1][1]) == collapse_ws(line):
        out.pop()
    return out[-_WINDOW:]


def _conversation(exchanges: Sequence[tuple[str, str]]) -> tuple[str, list[int]]:
    """The chat as the model reads it, user messages numbered, and where each number is."""
    lines: list[str] = []
    numbered: list[int] = []
    for index, (role, text) in enumerate(exchanges):
        if role == "user":
            numbered.append(index)
            lines.append(f"[{len(numbered)}] User: {collapse_ws(text)[:_USER_CHARS]}")
        else:
            lines.append(f"Assistant: {collapse_ws(text)[:_REPLY_CHARS]}")
    return "\n".join(lines), numbered


async def pick_referent(settings: Settings, line: str, conversation: str) -> ReferentPick | None:
    """The model's pick, or None when there is no read."""
    from app.core.redis import get_redis_client
    from app.gateways.structured_completion import complete_structured
    from app.services import quota as quota_service

    try:
        if await quota_service.global_spend_exceeded(get_redis_client(), settings):
            return None
        return await complete_structured(
            settings=settings,
            model_alias=ROUTING.referent_read,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {
                    "role": "user",
                    "content": f"Conversation:\n{conversation}\n\nLatest message: {line[:300]}",
                },
            ],
            schema=ReferentPick,
            max_tokens=20,
            timeout_seconds=settings.referent_read_timeout_seconds,
            allow_fallback=False,
            quiet_timeout=True,
        )
    except Exception as exc:  # A read is a hint: any failure leaves the turn as before.
        logger.info("referent read failed (%s)", type(exc).__name__)
        return None


# The turn's read, kept for the turn (``core.readings``): the photo intercept reads it first,
# and the subject solve asks again later in the same turn.
_KEPT = "referent"


async def referent_for_turn(
    settings: Settings, line: str, recent: Sequence[Any]
) -> Referent | None:
    """``read_referent`` once a turn: a later ask in the same turn gets the same read."""
    kept = kept_for_turn(_KEPT)
    if isinstance(kept, tuple) and kept[0] == line:
        referent: Referent | None = kept[1]
        return referent
    referent = await read_referent(settings, line, recent)
    keep_for_turn(_KEPT, (line, referent))
    return referent


async def read_referent(settings: Settings, line: str, recent: Sequence[Any]) -> Referent | None:
    """The earlier problem ``line`` asks to see, read by a model; None when there is no read
    (the line asks for none, the read is off, mocked, failed or too slow)."""
    if not settings.referent_read_enabled or not asks_for_a_referent(line):
        return None
    exchanges = _exchanges(recent, line)
    conversation, numbered = _conversation(exchanges)
    if not numbered:
        return None
    started = time.perf_counter()
    read = await pick_referent(settings, collapse_ws(line), conversation)
    logger.info("referent read took %.0f ms", (time.perf_counter() - started) * 1000)
    if read is None:
        return None
    if read.message is None:
        return Referent(None)
    if not 1 <= read.message <= len(numbered):
        return None
    return Referent(problem_at(exchanges, numbered[read.message - 1]).setup)
