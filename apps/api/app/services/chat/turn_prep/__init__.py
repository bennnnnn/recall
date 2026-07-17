"""Turn preparation — package split of the former turn_prep.py monolith.

Import surfaces preserved for callers and tests:
``from app.services.chat.turn_prep import X``
"""

from __future__ import annotations

from app.core.db import SessionLocal
from app.services.chat.turn_prep.attachments import (
    _AttachmentProcessResult,
    _process_attachments,
    count_image_attachments,
    vision_reserve_tokens,
)
from app.services.chat.turn_prep.context import (
    ClientGeoContext,
    RegenerateBackup,
    StreamContext,
    TurnPromptBundle,
    build_stream_prompt_context,
    resolve_client_geo,
    stream_context_from_bundle,
)
from app.services.chat.turn_prep.integrations import (
    INTEGRATION_LOAD_TIMEOUT_SECONDS,
    _inject_integration_blocks,
    _load_calendar_prompt_block,
    _load_gmail_context_block,
    _load_gmail_context_if_needed,
    _load_gmail_prompt_block,
    _load_has_calendar_write,
    _load_prior_user_messages,
    _timed_integration_load,
)
from app.services.chat.turn_prep.mode import (
    _classify_turn_mode,
    _resolve_instant_reply,
    _should_augment_web_and_tools,
    _should_minimal_quiz_context,
    _TurnMode,
)
from app.services.chat.turn_prep.prepare import (
    _grade_quiz_answer,
    prepare_chat_turn,
)

__all__ = [
    "INTEGRATION_LOAD_TIMEOUT_SECONDS",
    "ClientGeoContext",
    "RegenerateBackup",
    "SessionLocal",
    "StreamContext",
    "TurnPromptBundle",
    "_AttachmentProcessResult",
    "_TurnMode",
    "_classify_turn_mode",
    "_grade_quiz_answer",
    "_inject_integration_blocks",
    "_load_calendar_prompt_block",
    "_load_gmail_context_block",
    "_load_gmail_context_if_needed",
    "_load_gmail_prompt_block",
    "_load_has_calendar_write",
    "_load_prior_user_messages",
    "_process_attachments",
    "_resolve_instant_reply",
    "_should_augment_web_and_tools",
    "_should_minimal_quiz_context",
    "_timed_integration_load",
    "build_stream_prompt_context",
    "count_image_attachments",
    "prepare_chat_turn",
    "resolve_client_geo",
    "stream_context_from_bundle",
    "vision_reserve_tokens",
]
