"""Public Google Calendar and Gmail surface.

Importing ``modules.integrations.models`` must not load the service graph.
The package surface stays lazy so that import does not pull the service graph.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "calendar_nudge_redis_key": ("nudges", "calendar_nudge_redis_key"),
    "events_needing_nudge": ("nudges", "events_needing_nudge"),
    "fetch_upcoming_events": ("calendar", "fetch_upcoming_events"),
    "format_calendar_nudge": ("nudges", "format_calendar_nudge"),
    "is_external_calendar_question": ("calendar", "is_external_calendar_question"),
    "nudge_ttl_seconds": ("nudges", "nudge_ttl_seconds"),
}
__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(f"app.modules.integrations.{module_name}"), attribute)
    globals()[name] = value
    return value
