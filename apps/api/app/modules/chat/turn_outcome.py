"""What one turn produced, for the transport that carries it.

The intercepts, the pipeline and the finalize passes fill a ``TurnOutcome``; the
transports read it once the token stream ends, wait on its tasks, and send the
``stream_end`` and ``done`` events built from it (``stream_events``).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from app.modules.web_search import SearchSource


@dataclass
class TurnOutcome:
    """One turn's saved reply, what ``done`` says about it, and the work still running."""

    message_id: str | None = None
    # The reply as it persists, when that differs from the streamed text or the
    # reply was stopped.
    final_content: str | None = None
    resolved_model: str | None = None
    # The provider answered on another alias than the one asked for.
    fallback_used: bool = False
    # "interrupted" or "user_stop"; None when the reply completed.
    completion: str | None = None
    # How much of the reply the client had drawn when its user tapped Stop (a
    # UTF-16 length, from the cancel frame); a stopped reply saves no more.
    client_shown_chars: int | None = None
    recalled: int = 0
    memory_hints: list[str] = field(default_factory=list)
    context_summarized: int = 0
    search_sources: list[SearchSource] = field(default_factory=list)
    todos_changed: bool = False
    # The user message this turn answers is in the chat. An error frame says so
    # (``user_message_saved``): the phone offers Retry (resend) only when it is not,
    # and Regenerate only when it is. A regenerate answers a saved message.
    user_message_saved: bool = False
    # The commit ``done`` waits on, and the post-turn jobs that follow it.
    finalize_db_task: asyncio.Task[None] | None = None
    finalize_task: asyncio.Task[None] | None = None
    # The follow-up questions, sent after ``done``.
    related_task: asyncio.Task[dict[str, Any] | None] | None = None

    def mark_user_message_saved(self) -> None:
        self.user_message_saved = True
