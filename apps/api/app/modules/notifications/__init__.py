"""Notification delivery services.

The package stays lazy so importing it does not load the push sender.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "channel_id_for_token": ("push", "channel_id_for_token"),
    "PUSH_SOUND": ("push", "PUSH_SOUND"),
}
__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(f"app.modules.notifications.{module_name}"), attribute)
    globals()[name] = value
    return value
