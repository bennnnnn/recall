"""Chat — history over HTTP and the streamed turn (WebSocket and SSE).

``api`` / ``service`` serve ``/chats``. ``ws_api`` (preferred, supports stop)
and ``stream_api`` (SSE fallback) carry a turn; ``stream`` is the facade both
call, and ``turn_prep`` → ``stream_pipeline`` → ``post_turn`` are the stages
behind it (CLAUDE.md, "The chat loop").

The package stays lazy. Other modules import a few small helpers from here —
turn cues, reply presentation, stream status — and that must not load the
stream stack, which itself imports those modules. Other modules import only
the names below.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "RegenerateBackup": ("turn_prep", "RegenerateBackup"),
    "StreamContext": ("turn_prep", "StreamContext"),
    "StreamStatusFn": ("stream_status", "StreamStatusFn"),
    "clip_status_detail": ("stream_status", "clip_status_detail"),
    "has_locale_cue": ("prompt_constants.locale_cues", "has_locale_cue"),
    "is_lightweight_chat_turn": ("prompt_constants.routing", "is_lightweight_chat_turn"),
    "is_personal_disclosure_turn": ("prompt_constants.routing", "is_personal_disclosure_turn"),
    "is_short_confirmation": ("prompt_constants.routing", "is_short_confirmation"),
    "needs_generated_title": ("titles", "needs_generated_title"),
    "present_assistant_markdown": ("presentation", "present_assistant_markdown"),
    "prior_looks_like_offer": ("prompt_constants.routing", "prior_looks_like_offer"),
    "stream_chat_response": ("stream", "stream_chat_response"),
    "stream_regenerate_response": ("stream", "stream_regenerate_response"),
}
_MODULE_EXPORTS = (
    "compaction",
    "history_rag",
    "service",
    "stream",
    "stream_entry",
    "stream_pipeline",
    "titles",
    "tools",
    "turn_resources",
)

__all__ = [*_EXPORTS, *_MODULE_EXPORTS]


def __getattr__(name: str) -> Any:
    if name in _MODULE_EXPORTS:
        value = import_module(f"app.modules.chat.{name}")
    else:
        target = _EXPORTS.get(name)
        if target is None:
            raise AttributeError(name)
        module_name, attribute = target
        value = getattr(import_module(f"app.modules.chat.{module_name}"), attribute)
    globals()[name] = value
    return value
