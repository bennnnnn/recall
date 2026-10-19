"""Finalize passes for the server's part of a multi-part reply.

"Switch to dark mode and tell me a joke": the model tells the joke and the settings
card goes under it. "Draw a cat wearing a hat and also explain black holes": the
picture drawn beside the answer goes above it, or a line says why it could not.
``chat/finalize_passes.py`` lists them in order. Both commit the text: ``done``
carries what they added, so a later pass's failure keeps it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.chat.finalize_subjects import fallback_text
from app.modules.images.reply_picture import ReplyPicture
from app.services.md_fence_scan import strip_closed_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

_SETTINGS_FENCE = "settings_proposal"


async def attach_reply_picture(state: FinalizeState) -> str:
    """The picture above the reply. A stopped reply draws nothing (its slot comes back)."""
    ctx = state.ctx
    picture = ctx.reply_picture
    if not isinstance(picture, ReplyPicture):
        return state.text
    if state.was_cancelled or (state.should_cancel is not None and state.should_cancel()):
        picture.cancel()
        return state.text
    text, ids = await picture.attach(state.text)
    # After the answer photo's pass, which sets the list: the picture is linked beside it.
    ctx.answer_photo_ids = [*ctx.answer_photo_ids, *ids]
    state.committed = fallback_text(text, server_text=state.server_text)
    return text


def add_settings_card(state: FinalizeState) -> str:
    """The server's settings card under the reply; a card the model wrote is not one."""
    card = state.ctx.settings_card
    if not isinstance(card, str) or not card:
        return state.text
    text = strip_closed_fences(state.text, _SETTINGS_FENCE).rstrip()
    text = f"{text}\n\n{card}" if text else card
    state.committed = fallback_text(text, server_text=state.server_text)
    return text
