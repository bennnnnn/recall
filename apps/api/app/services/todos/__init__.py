"""Reminders & Lists service — public re-export barrel.

Callers: ``from app.services import todos as todos_service``.
Private helpers live in submodules; import those directly when needed.
"""

from __future__ import annotations

from app.services.todos.actions import (
    MAX_TODO_ACTIONS_PER_TURN,
    REMINDER_TOPIC,
    TODO_BLOCKED_FROM_TRANSCRIPT,
    apply_todo_actions,
)
from app.services.todos.classification import (
    query_implies_todos,
    should_pre_sync_todos,
    transcript_implies_todo_sync,
)
from app.services.todos.prompt_context import (
    build_todos_system_section,
    format_todos_block,
    load_todos_for_prompt,
    select_todos_for_prompt,
    should_inject_todos_prompt,
)
from app.services.todos.prompt_hint import TODO_HINT
from app.services.todos.reminder_fences import materialize_reminder_fences
from app.services.todos.sync import (
    TODO_SYNC_FEEDBACK_HEADER,
    TODO_SYNC_RECENT_MESSAGES,
    build_todo_sync_transcript,
    format_chat_transcript,
    format_todo_sync_feedback,
    sync_todos_before_reply,
    sync_todos_from_transcript,
)

__all__ = [
    "MAX_TODO_ACTIONS_PER_TURN",
    "REMINDER_TOPIC",
    "TODO_BLOCKED_FROM_TRANSCRIPT",
    "TODO_HINT",
    "TODO_SYNC_FEEDBACK_HEADER",
    "TODO_SYNC_RECENT_MESSAGES",
    "apply_todo_actions",
    "build_todo_sync_transcript",
    "build_todos_system_section",
    "format_chat_transcript",
    "format_todo_sync_feedback",
    "format_todos_block",
    "load_todos_for_prompt",
    "materialize_reminder_fences",
    "query_implies_todos",
    "select_todos_for_prompt",
    "should_inject_todos_prompt",
    "should_pre_sync_todos",
    "sync_todos_before_reply",
    "sync_todos_from_transcript",
    "transcript_implies_todo_sync",
]
