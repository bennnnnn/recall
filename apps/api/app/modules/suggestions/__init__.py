"""Proactive follow-up suggestions from recent chat and memory."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_MODULE_EXPORTS = ("repository",)
__all__ = list(_MODULE_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _MODULE_EXPORTS:
        raise AttributeError(name)
    value = import_module(f"app.modules.suggestions.{name}")
    globals()[name] = value
    return value
