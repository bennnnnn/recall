"""Plan and store-billing surface.

The package stays lazy so importing it does not load RevenueCat or the webhook.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "is_pro": ("plan", "is_pro"),
}
__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(f"app.modules.billing.{module_name}"), attribute)
    globals()[name] = value
    return value
