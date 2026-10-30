"""Recall's own prompt rules as one text: what a reply must never say back to the user.

Only the fixed rules (chat's prompt constants and each subject's hints), never a turn's
context: a saved memory, a to-do, a document or a search result is the user's own, and a
reply quoting "Use a heavy-based pan" from their recipe quotes them, not the prompt
(review, 2026-10-30).
"""

from __future__ import annotations

import importlib
import pkgutil
from functools import cache

from app.modules.chat import prompt_constants
from app.modules.chat.prompt_subjects import SUBJECT_HINTS

# A rule is a sentence or more; a short constant is a label or a word list.
_MIN_RULE = 40


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if len(value) >= _MIN_RULE else []
    if isinstance(value, tuple | list | frozenset | set):
        return [text for item in value for text in _strings(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    return []


@cache
def prompt_rule_text() -> str:
    """Every fixed rule the chat prompt may carry, joined."""
    rules: list[str] = []
    for info in pkgutil.iter_modules(prompt_constants.__path__):
        module = importlib.import_module(f"{prompt_constants.__name__}.{info.name}")
        for name, value in vars(module).items():
            if name.isupper() or (name.startswith("_") and name.lstrip("_").isupper()):
                rules += _strings(value)
    for hints in SUBJECT_HINTS.values():
        for short in (False, True):
            rules += _strings(list(hints.presentation(short)))
        rules += _strings(hints.closing)
    return "\n".join(rules)
