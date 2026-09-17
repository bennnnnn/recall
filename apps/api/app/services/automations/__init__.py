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
from app.services.automations.fences import (
    format_automation_confirm_fence,
    materialize_automation_fences,
)
from app.services.automations.prompt_hint import AUTOMATIONS_HINT

__all__ = [
    "AUTOMATIONS_HINT",
    "AutomationsError",
    "create_automation",
    "delete_automation",
    "format_automation_confirm_fence",
    "get_automation",
    "list_automations",
    "materialize_automation_fences",
    "update_automation",
]
