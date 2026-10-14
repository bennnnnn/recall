"""Turn preparation — package split of the former turn_prep.py monolith.

Import surfaces preserved for callers and tests:
``from app.modules.chat.turn_prep import X``
"""

from __future__ import annotations

from app.core.db import SessionLocal
from app.modules.chat.turn_prep.attachments import (
    _AttachmentProcessResult,
    _process_attachments,
    count_image_attachments,
    vision_reserve_tokens,
)
from app.modules.chat.turn_prep.context import (
    ClientGeoContext,
    RegenerateBackup,
    StreamContext,
    TurnPromptBundle,
    _load_prior_user_messages,
    await_user_message_persist,
    build_stream_prompt_context,
    resolve_client_geo,
    stream_context_from_bundle,
)
from app.modules.chat.turn_prep.mode import (
    _classify_turn_mode,
    _should_augment_web_and_tools,
    _TurnMode,
)
from app.modules.chat.turn_prep.prepare import (
    prepare_chat_turn,
)

__all__ = [
    "ClientGeoContext",
    "RegenerateBackup",
    "SessionLocal",
    "StreamContext",
    "TurnPromptBundle",
    "_AttachmentProcessResult",
    "_TurnMode",
    "_classify_turn_mode",
    "_load_prior_user_messages",
    "_process_attachments",
    "_should_augment_web_and_tools",
    "await_user_message_persist",
    "build_stream_prompt_context",
    "count_image_attachments",
    "prepare_chat_turn",
    "resolve_client_geo",
    "stream_context_from_bundle",
    "vision_reserve_tokens",
]
