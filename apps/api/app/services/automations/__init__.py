"""Automations service — public re-export barrel.

Callers: ``from app.services import automations as automations_service`` or
``from app.services.automations import crud as automations_crud``.
"""

from __future__ import annotations

from app.services.automations.crud import (
    AutomationsError,
    create_automation,
    delete_automation,
    get_automation,
    list_automations,
    update_automation,
)

__all__ = [
    "AutomationsError",
    "create_automation",
    "delete_automation",
    "get_automation",
    "list_automations",
    "update_automation",
]
