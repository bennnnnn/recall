"""A reply cut off inside its ```reminder fence reaches the reminder pass without it."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat.finalize_reminders import apply_reminder_pass, drop_cut_reminder_fence
from app.modules.chat.turn_prep.context import StreamContext
from app.services.md_fence_scan import close_unclosed_fences
from app.tests.modules.chat.chat_test_support import turn_deps

_CUT = 'Sure.\n\n```reminder\n{"title": "Dentist", "due_at": "2026-10-15T15:00'
_CLOSED = 'Sure.\n\n```reminder\n{"title": "Dentist"}\n```'


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        (_CUT, "Sure."),
        ('```reminder\n{"title": "Den', ""),
        ("Here:\n\n```Reminder\n{", "Here:"),
        (f"```python\nprint(1)\n```\n\n{_CUT}", "```python\nprint(1)\n```\n\nSure."),
        # Closed fences, other open fences and plain prose are not the reminder pass's.
        (_CLOSED, _CLOSED),
        ("Sure.\n\n```python\nprint(1", "Sure.\n\n```python\nprint(1"),
        ('```reminder_proposal\n{"proposal_id": "a"', '```reminder_proposal\n{"proposal_id": "a"'),
        ("No fences at all.", "No fences at all."),
    ],
)
def test_drop_cut_reminder_fence_drops_only_an_open_reminder_fence(text: str, kept: str) -> None:
    assert drop_cut_reminder_fence(text) == kept


def test_a_dropped_fence_leaves_nothing_for_the_fence_repair_to_close() -> None:
    assert close_unclosed_fences(drop_cut_reminder_fence(_CUT)) == "Sure."


@pytest.mark.asyncio
async def test_a_reply_emptied_by_the_reminder_pass_asks_when() -> None:
    """A reply that was only a fence, with nothing saved, came back empty: done
    carried nothing, so the phone kept the streamed fence."""
    deps = turn_deps(todos={"materialize_reminder_fences": AsyncMock(return_value=("", 0))})
    ctx = SimpleNamespace(
        user=MagicMock(timezone="UTC"),
        user_id=uuid4(),
        chat_id=uuid4(),
        user_timezone="UTC",
        user_message_content="remind me to plate the dinner",
        prompt_messages=[],
        skip_memory_jobs=True,
    )
    text = await apply_reminder_pass(
        deps, AsyncMock(), Settings(), cast(StreamContext, ctx), _CLOSED, None
    )
    assert text == "When should I remind you?"


@pytest.mark.asyncio
@pytest.mark.parametrize(("created", "changed"), [(0, False), (2, True)])
async def test_the_list_is_flagged_changed_only_when_rows_were_written(
    created: int, changed: bool
) -> None:
    """``todos_changed`` sent the phone to reload its list three times for a background
    extraction that no longer exists (code-health audit NET-14)."""
    from app.modules.chat.turn_outcome import TurnOutcome

    deps = turn_deps(
        todos={"materialize_reminder_fences": AsyncMock(return_value=("Done.", created))}
    )
    ctx = SimpleNamespace(
        user=MagicMock(timezone="UTC"),
        user_id=uuid4(),
        chat_id=uuid4(),
        user_timezone="UTC",
        user_message_content="yes, move them all to tomorrow",
        prompt_messages=[],
        skip_memory_jobs=False,
    )
    outcome = TurnOutcome()
    await apply_reminder_pass(
        deps, AsyncMock(), Settings(), cast(StreamContext, ctx), "Done.", outcome
    )
    assert outcome.todos_changed is changed


def _ctx(message: str, locale: str = "en") -> StreamContext:
    return cast(
        StreamContext,
        SimpleNamespace(
            user=MagicMock(timezone="UTC", locale=locale),
            user_id=uuid4(),
            chat_id=uuid4(),
            user_timezone="UTC",
            user_message_content=message,
            prompt_messages=[],
            skip_memory_jobs=True,
        ),
    )


_SPANISH = "recuérdame mañana a las 9 llamar a mamá"
_LINK = "```todo_link\n```"
_ES_LINE = "Puedes añadirlo o cambiarlo en **Tareas**."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        # The model wrote a reminder anyway: no card, the To-do button instead.
        (
            'Claro.\n\n```reminder\n{"title": "Llamar a mamá", "due_at": "2026-10-24T09:00:00"}\n```',
            f"Claro.\n\n{_LINK}",
        ),
        # A reply with no words of its own still says, in Spanish, where to go.
        ('```reminder\n{"title": "Llamar a mamá"}\n```', f"{_ES_LINE}\n\n{_LINK}"),
        (_LINK, f"{_ES_LINE}\n\n{_LINK}"),
        # A search the model made (the time zone) cites nothing above the button.
        (
            f'```sources\n[{{"title": "EAT", "url": "https://time.example"}}]\n```\n\n{_LINK}',
            f"{_ES_LINE}\n\n{_LINK}",
        ),
        # The model already offered the button: it stays, once, last.
        (f"Puedes añadirlo en Tareas.\n\n{_LINK}", f"Puedes añadirlo en Tareas.\n\n{_LINK}"),
        # A read of the list is left as it is.
        ("Hoy tienes: llamar a mamá.", "Hoy tienes: llamar a mamá."),
    ],
)
async def test_a_message_in_another_language_gets_the_todo_button_not_a_card(
    reply: str, kept: str
) -> None:
    materialize = AsyncMock(return_value=("unused", 1))
    deps = turn_deps(todos={"materialize_reminder_fences": materialize})
    text = await apply_reminder_pass(deps, AsyncMock(), Settings(), _ctx(_SPANISH), reply, None)
    # Exactly the kept reply: never the English "when?" the reminder pass answers with.
    assert text == kept
    materialize.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "locale", "line"),
    [
        ("напомни завтра в 9 позвонить маме", "en", "Добавить или изменить это можно в разделе **Задачи**."),
        ("ነገ 9 ሰዓት እናቴን እንድደውል አስታውሰኝ", "en", "በ**የሚደረጉ** ውስጥ ማከል ወይም መቀየር ይችላሉ።"),
        ("rappelle-moi demain à 9h d'appeler maman", "en", "Vous pouvez l'ajouter ou le modifier dans **Tâches**."),
        ("erinnere mich morgen um 9 Uhr, Mama anzurufen", "es", "Du kannst das unter **Aufgaben** hinzufügen oder ändern."),
        # A language the app has no line for: the user's own app language, then English.
        ("ذكرني غدا الساعة 9 بالاتصال بأمي", "es", _ES_LINE),
        ("ذكرني غدا الساعة 9 بالاتصال بأمي", "en", "You can add or change it in **To-do**."),
    ],
)  # fmt: skip
async def test_the_line_above_a_bare_button_is_in_the_message_s_language(
    message: str, locale: str, line: str
) -> None:
    deps = turn_deps(todos={"materialize_reminder_fences": AsyncMock()})
    text = await apply_reminder_pass(
        deps, AsyncMock(), Settings(), _ctx(message, locale), _LINK, None
    )
    assert text == f"{line}\n\n{_LINK}"


@pytest.mark.asyncio
async def test_an_english_message_still_reaches_the_reminder_pass() -> None:
    materialize = AsyncMock(return_value=("Saved.", 1))
    deps = turn_deps(todos={"materialize_reminder_fences": materialize})
    text = await apply_reminder_pass(
        deps, AsyncMock(), Settings(), _ctx("remind me to call mom at 9"), _CLOSED, None
    )
    assert text == "Saved."
    materialize.assert_awaited_once()
