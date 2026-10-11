"""Public Memory surface.

Importing ``modules.memory.models`` must not load this service graph, or
SQLAlchemy's model registry cycles on ``Memory``. Wrappers live in
``surface`` and are installed on this package on first use so existing
monkeypatches of ``app.modules.memory`` still hit the seam.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


def __getattr__(name: str) -> Any:
    if name.startswith("__"):
        raise AttributeError(name)
    value = getattr(import_module("app.modules.memory.surface"), name)
    globals()[name] = value
    return value


# The chat turn answers "what do you know about me" from here.
_MODULE_EXPORTS = ("profile_reply",)
# Names other modules import from this package (resolved through ``surface``).
__all__ = [
    "invalidate_memory_block",
    "is_explicit_memory_command",
    "is_food_or_diet_query",
    "list_for_user",
    "list_range",
    "memory_extract_user_text",
]
