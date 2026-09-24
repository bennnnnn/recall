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
    "TODO_SYNC_RECENT_MESSAGES": ("sync", "TODO_SYNC_RECENT_MESSAGES"),
    "TodosPromptSections": ("prompt_context", "TodosPromptSections"),
    "apply_todo_actions": ("actions", "apply_todo_actions"),
    "build_todo_sync_transcript": ("sync", "build_todo_sync_transcript"),
    "build_todos_system_section": ("prompt_context", "build_todos_system_section"),
    "format_chat_transcript": ("sync", "format_chat_transcript"),
    "format_todos_block": ("prompt_context", "format_todos_block"),
    "format_todos_voice_block": ("prompt_context", "format_todos_voice_block"),
    "materialize_reminder_fences": ("reminder_fences", "materialize_reminder_fences"),
    "query_implies_todos": ("classification", "query_implies_todos"),
    "select_todos_for_prompt": ("prompt_context", "select_todos_for_prompt"),
    "should_inject_todos_prompt": ("prompt_context", "should_inject_todos_prompt"),
    "TodoEmailSnapshot": ("email_repository", "TodoEmailSnapshot"),
    "TodoScheduleSnapshot": ("schedule_repository", "TodoScheduleSnapshot"),
    "is_recurrence_rule": ("recurrence", "is_recurrence_rule"),
    "mark_email_sent_if_current": ("email_repository", "mark_email_sent_if_current"),
    "next_recurring_due": ("recurrence", "next_recurring_due"),
    "snap_first_due": ("recurrence", "snap_first_due"),
    "sync_todos_from_transcript": ("sync", "sync_todos_from_transcript"),
    "update_schedule_if_current": ("schedule_repository", "update_schedule_if_current"),
    "transcript_implies_todo_sync": ("classification", "transcript_implies_todo_sync"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(f"app.modules.todos.{module_name}"), attribute)
    globals()[name] = value
    return value
