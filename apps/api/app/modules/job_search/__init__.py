"""My Job module.

Consumers should import the smallest public surface they need, such as
``app.modules.job_search.service`` or ``app.modules.job_search.chat_intent``.
The package initializer stays dependency-free so SQLAlchemy can discover the
module-owned models without creating an import cycle.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {"suspend_on_expiration": ("billing_events", "suspend_on_expiration")}
__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(f"app.modules.job_search.{module_name}"), attribute)
    globals()[name] = value
    return value
