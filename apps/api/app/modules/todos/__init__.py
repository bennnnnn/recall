"""Public, lazily loaded surface for the Todos domain.

Keeping this package initializer lazy lets the central SQLAlchemy metadata
registry import ``modules.todos.models`` without loading the service graph.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "MAX_TODO_ACTIONS_PER_TURN": ("actions", "MAX_TODO_ACTIONS_PER_TURN"),
    "REMINDER_TOPIC": ("actions", "REMINDER_TOPIC"),
    "TODO_HINT": ("prompt_hint", "TODO_HINT"),
    "apply_todo_actions": ("actions", "apply_todo_actions"),
    "build_todos_system_section": ("prompt_context", "build_todos_system_section"),
    "format_todos_voice_block": ("prompt_context", "format_todos_voice_block"),
    "materialize_reminder_fences": ("reminder_fences", "materialize_reminder_fences"),
    "reminder_cards_as_text": ("proposals", "cards_as_text"),
    "query_implies_todos": ("classification", "query_implies_todos"),
    "select_todos_for_prompt": ("prompt_context", "select_todos_for_prompt"),
    "TodoEmailSnapshot": ("email_repository", "TodoEmailSnapshot"),
    "EMAIL_REMINDERS": ("due_reminders", "EMAIL"),
    "PUSH_REMINDERS": ("due_reminders", "PUSH"),
    "due_reminder_page": ("due_reminders", "due_reminder_page"),
    "is_due_now": ("due_reminders", "is_due_now"),
    "reminder_page_key": ("due_reminders", "page_key"),
    "tokenless_recurring_overdue": ("due_reminders", "tokenless_recurring_overdue"),
    "TodoScheduleSnapshot": ("schedule_repository", "TodoScheduleSnapshot"),
    "is_recurrence_rule": ("recurrence", "is_recurrence_rule"),
    "mark_email_sent_if_current": ("email_repository", "mark_email_sent_if_current"),
    "next_recurring_due": ("recurrence", "next_recurring_due"),
    "snap_first_due": ("recurrence", "snap_first_due"),
    "update_schedule_if_current": ("schedule_repository", "update_schedule_if_current"),
}

_MODULE_EXPORTS = ("repository",)
__all__ = list(_EXPORTS) + list(_MODULE_EXPORTS)


def __getattr__(name: str) -> Any:
    if name in _MODULE_EXPORTS:
        value = import_module(f"app.modules.todos.{name}")
        globals()[name] = value
        return value
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(f"app.modules.todos.{module_name}"), attribute)
    globals()[name] = value
    return value
