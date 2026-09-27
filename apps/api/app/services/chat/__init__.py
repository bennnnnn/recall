"""Chat turn orchestration — lazily loaded public entrypoints and key types.

Web-search classification imports chat prompt constants. Keeping this package
initializer lazy prevents that narrow import from eagerly loading the complete
stream stack, which itself imports web search and otherwise exposes a partially
initialized compatibility module.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "RegenerateBackup": ("turn_prep", "RegenerateBackup"),
    "StreamContext": ("turn_prep", "StreamContext"),
    "StreamStatusFn": ("prompt_builder", "StreamStatusFn"),
    "stream_chat_response": ("stream", "stream_chat_response"),
    "stream_regenerate_response": ("stream", "stream_regenerate_response"),
}
_MODULE_EXPORTS = {
    "history_rag",
    "stream",
    "stream_entry",
    "stream_pipeline",
    "tools",
    "turn_resources",
}

__all__ = [*_EXPORTS, *_MODULE_EXPORTS]


def __getattr__(name: str) -> Any:
    if name in _MODULE_EXPORTS:
        value = import_module(f"app.services.chat.{name}")
    else:
        target = _EXPORTS.get(name)
        if target is None:
            raise AttributeError(name)
        module_name, attribute = target
        value = getattr(import_module(f"app.services.chat.{module_name}"), attribute)
    globals()[name] = value
    return value
