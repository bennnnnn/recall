"""Which of the turn's requests are still open for a tool.

The gates used to read the whole message as one request, so one part could cancel
another: "remind me to buy milk and what's the weather in Nairobi?" never searched
(a reminder turn skips search), nor did "teach me dictionaries, and what is the
price of bitcoin?" (a request to make something asks nothing to look up), and a
verified "solve 2x + 5 = 17" skipped the loop the weather half needed. Each gate now
asks per part of the turn's plan (``turn_prep.intents``). A one-part message (nearly
every turn) is the whole message, exactly as before.
"""

from __future__ import annotations

from app.core.config import Settings
from app.modules.turn_reading.plan import HANDLED_KINDS


def open_parts(
    text: str, *, has_verified_math: bool = False, settings: Settings | None = None
) -> list[str]:
    """The requests still open for a tool, each in the user's own words.

    One part is the whole message, or nothing once its solve is verified. On a
    multi-part plan the verified solve answers only its maths part, and the
    settings, picture and photo parts belong to their own paths, never the loop's.
    """
    from app.modules.chat.turn_prep.reading import plan_of

    plan = plan_of(text, settings)
    if not plan.multi:
        return [] if has_verified_math else [text]
    done = {*HANDLED_KINDS, "solve"} if has_verified_math else set(HANDLED_KINDS)
    return [part.text for part in plan.parts if part.kind not in done]
