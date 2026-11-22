"""Whether a message asks for a photo or a painted picture, as the turn's read says.

For the phone's composer (``POST /images/intent``), which asks before a send that might be
a picture: the same read every chat turn starts (``turn_decision``), on the message and the
chat's last turns, with each picture shown in them said in words (``shown_pictures``). The
chat turn's own intercept waits for its turn's read instead (``drawn_picture.read_asks_it``).
None whenever the read gives no answer in time: the send then goes to chat, and nothing is
drawn or looked up on a guess.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, Literal
from uuid import UUID

from app.core.config import Settings
from app.modules.chat import shown_pictures
from app.modules.chat.drawn_picture import read_asks
from app.modules.chat.shown_pictures import ShownPicture, ShownPictures
from app.modules.chat.turn_decision import start_turn_decision

PictureAsk = Literal["photo", "image"]
# The read ends by its own budget (``live_read_timeout_seconds``); this only bounds a stuck one.
_GRACE = 0.5


async def picture_labels(user_id: UUID, rows: Sequence[Any]) -> dict[UUID, ShownPicture]:
    """What each picture the assistant's ``rows`` show was (``shown_pictures``)."""
    return dict(await shown_pictures.settled_labels(shown_pictures.start_labels(user_id, rows)))


async def read_picture_ask(
    settings: Settings,
    text: str,
    recent: Sequence[Any],
    *,
    pictures: ShownPictures | None = None,
) -> PictureAsk | None:
    """``photo`` or ``image`` when the read says ``text`` asks for one, else None."""
    labels: asyncio.Future[dict[UUID, ShownPicture]] = asyncio.get_running_loop().create_future()
    labels.set_result(dict(pictures or {}))
    task = start_turn_decision(settings, text, recent=list(recent), pictures=labels)
    if task is None:
        return None
    try:
        decision = await asyncio.wait_for(task, settings.live_read_timeout_seconds + _GRACE)
    except TimeoutError:
        return None
    if read_asks(decision, "image"):
        return "image"
    return "photo" if read_asks(decision, "photo") else None
