"""Turn preparation: attachments, the user's row, the prompt and its context.

The package exports what the stream stages and tests read; everything else is
imported from its own submodule.
"""

from __future__ import annotations

from app.modules.chat.turn_prep.attachments import count_image_attachments, vision_reserve_tokens
from app.modules.chat.turn_prep.context import (
    RegenerateBackup,
    StreamContext,
    TurnPromptBundle,
    await_user_message_persist,
    build_stream_prompt_context,
    stream_context_from_bundle,
)
from app.modules.chat.turn_prep.prepare import prepare_chat_turn
from app.modules.chat.turn_prep.request import (
    ClientGeoContext,
    TurnRequest,
    resolve_client_geo,
)

__all__ = [
    "ClientGeoContext",
    "RegenerateBackup",
    "StreamContext",
    "TurnPromptBundle",
    "TurnRequest",
    "await_user_message_persist",
    "build_stream_prompt_context",
    "count_image_attachments",
    "prepare_chat_turn",
    "resolve_client_geo",
    "stream_context_from_bundle",
    "vision_reserve_tokens",
]
