"""Public, lazily loaded surface for the Todos domain.

Keeping this package initializer lazy lets the central SQLAlchemy metadata
registry import ``modules.todos.models`` without loading the service graph.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.modules.todos.chat_language import (
        TODO_LINK_FENCE as TODO_LINK_FENCE,
    )
    from app.modules.todos.chat_language import (
        answer_language as answer_language,
    )
    from app.modules.todos.chat_language import (
        language_evidence as language_evidence,
    )
    from app.modules.todos.chat_language import (
        message_language as message_language,
    )
    from app.modules.todos.chat_language import (
        todo_screen_answer as todo_screen_answer,
    )
    from app.modules.todos.chat_language import (
        todo_screen_line as todo_screen_line,
    )
    from app.modules.todos.classification import (
        names_a_todo as names_a_todo,
    )
    from app.modules.todos.classification import (
        query_implies_todos as query_implies_todos,
    )
    from app.modules.todos.due_reminders import (
        EMAIL_REMINDERS as EMAIL_REMINDERS,
    )
    from app.modules.todos.due_reminders import (
        PUSH_REMINDERS as PUSH_REMINDERS,
    )
    from app.modules.todos.due_reminders import (
        advance_recurring_without_device as advance_recurring_without_device,
    )
    from app.modules.todos.due_reminders import (
        aged_out_unsent as aged_out_unsent,
    )
    from app.modules.todos.due_reminders import (
        due_reminder_page as due_reminder_page,
    )
    from app.modules.todos.due_reminders import (
        is_due_now as is_due_now,
    )
    from app.modules.todos.due_reminders import (
        mark_reminder_emailed as mark_reminder_emailed,
    )
    from app.modules.todos.due_reminders import (
        mark_reminders_pushed as mark_reminders_pushed,
    )
    from app.modules.todos.due_reminders import (
        reminder_page_key as reminder_page_key,
    )
    from app.modules.todos.limits import (
        AccountShare as AccountShare,
    )
    from app.modules.todos.limits import (
        TodoLimitError as TodoLimitError,
    )
    from app.modules.todos.occurrences import (
        TodoEmailSnapshot as TodoEmailSnapshot,
    )
    from app.modules.todos.prompt_context import (
        build_todos_system_section as build_todos_system_section,
    )
    from app.modules.todos.prompt_context import (
        format_todos_voice_block as format_todos_voice_block,
    )
    from app.modules.todos.prompt_context import (
        select_todos_for_prompt as select_todos_for_prompt,
    )
    from app.modules.todos.prompt_hint import (
        TODO_HINT as TODO_HINT,
    )
    from app.modules.todos.read_asks import (
        asks_to_read_reminders as asks_to_read_reminders,
    )
    from app.modules.todos.reading import (
        read_back as read_back,
    )
    from app.modules.todos.reading import (
        saved_todo_named as saved_todo_named,
    )
    from app.modules.todos.reply_claims import (
        claims_change as claims_change,
    )
    from app.modules.todos.reply_claims import (
        without_claims as without_claims,
    )
    from app.modules.todos.reply_offers import (
        asks_when as asks_when,
    )
    from app.modules.todos.reply_offers import (
        without_reminder_offers as without_reminder_offers,
    )
    from app.modules.todos.spoken_when import (
        is_only_a_when as is_only_a_when,
    )
    from app.modules.todos.write_asks import (
        todo_screen_reply as todo_screen_reply,
    )
    from app.modules.todos.write_asks_english import (
        asks_in_english as asks_in_english,
    )

_EXPORTS = {
    "TODO_HINT": ("prompt_hint", "TODO_HINT"),
    "TODO_LINK_FENCE": ("chat_language", "TODO_LINK_FENCE"),
    "answer_language": ("chat_language", "answer_language"),
    "asks_in_english": ("write_asks_english", "asks_in_english"),
    "asks_to_read_reminders": ("read_asks", "asks_to_read_reminders"),
    "build_todos_system_section": ("prompt_context", "build_todos_system_section"),
    "claims_change": ("reply_claims", "claims_change"),
    "format_todos_voice_block": ("prompt_context", "format_todos_voice_block"),
    "is_only_a_when": ("spoken_when", "is_only_a_when"),
    "language_evidence": ("chat_language", "language_evidence"),
    "message_language": ("chat_language", "message_language"),
    "query_implies_todos": ("classification", "query_implies_todos"),
    "read_back": ("reading", "read_back"),
    "saved_todo_named": ("reading", "saved_todo_named"),
    "names_a_todo": ("classification", "names_a_todo"),
    "asks_when": ("reply_offers", "asks_when"),
    "select_todos_for_prompt": ("prompt_context", "select_todos_for_prompt"),
    "todo_screen_answer": ("chat_language", "todo_screen_answer"),
    "todo_screen_line": ("chat_language", "todo_screen_line"),
    "todo_screen_reply": ("write_asks", "todo_screen_reply"),
    "without_claims": ("reply_claims", "without_claims"),
    "without_reminder_offers": ("reply_offers", "without_reminder_offers"),
    "TodoEmailSnapshot": ("occurrences", "TodoEmailSnapshot"),
    "AccountShare": ("limits", "AccountShare"),
    "TodoLimitError": ("limits", "TodoLimitError"),
    "EMAIL_REMINDERS": ("due_reminders", "EMAIL_REMINDERS"),
    "PUSH_REMINDERS": ("due_reminders", "PUSH_REMINDERS"),
    "advance_recurring_without_device": ("due_reminders", "advance_recurring_without_device"),
    "aged_out_unsent": ("due_reminders", "aged_out_unsent"),
    "due_reminder_page": ("due_reminders", "due_reminder_page"),
    "is_due_now": ("due_reminders", "is_due_now"),
    "mark_reminder_emailed": ("due_reminders", "mark_reminder_emailed"),
    "mark_reminders_pushed": ("due_reminders", "mark_reminders_pushed"),
    "reminder_page_key": ("due_reminders", "reminder_page_key"),
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
