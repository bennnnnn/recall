"""What a turn reads from memory, and what the prompt says when memory can't help.

M2 (work turns carry the stack), M8 (memory off / paused), M14 (the switch stops
past-chat recall), M16 (no record of an earlier chat), M17 (a failed read is said).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import Chat, User
from app.modules.chat import prompt_memory
from app.modules.chat.prompt_builder import _context_plan, build_prompt_messages
from app.modules.chat.prompt_constants import PROFILE_FACT_HINT
from app.modules.chat.prompt_context import _PromptContextBlocks
from app.modules.memory.switch import memory_switch_on
from app.tests.modules.chat.chat_test_support import system_prompt


def _user(*, memory: bool = True) -> User:
    return User(
        id=uuid4(),
        name="Bini",
        email="bini@example.com",
        plan="free",
        response_tone="casual",
        locale="en",
        timezone="Africa/Nairobi",
        memory_enabled=memory,
    )


async def _plan(text: str, *, memory: bool = True, rich: bool = False, advice: bool = False):
    return await _context_plan(
        _user(memory=memory),
        uuid4(),
        Settings(chat_history_rag_enabled=True, attachment_rag_enabled=False),
        query_text=text,
        minimal_personal_context=False,
        lightweight=False,
        rich_context=rich,
        advice_memory=advice,
        probe_attachment_rag=False,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "How should I structure auth in my app?",
        "How should I deploy my backend?",
        "Which state management library should I use?",
        "Write a login screen for me",
    ],
)
async def test_a_programming_turn_reads_the_work_scope(text):
    plan = await _plan(text)
    assert plan.load_memory is True
    assert plan.memory_scope == "work"
    # The stack comes without a query embed or a past-chat search.
    assert plan.history_rag is False


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["what is the capital of France", "tell me a joke"])
async def test_a_general_question_reads_no_memory(text):
    plan = await _plan(text)
    assert plan.load_memory is False
    assert plan.history_rag is False


@pytest.mark.asyncio
async def test_memory_off_stops_saved_facts_and_past_chat_recall():
    """M14: memory_enabled=False means no saved facts and no history RAG."""
    plan = await _plan("what did we decide last time about my wedding?", memory=False, rich=True)
    assert plan.load_memory is False
    assert plan.history_rag is False
    on = await _plan("what did we decide last time about my wedding?", rich=True)
    assert on.load_memory is True and on.history_rag is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "scope"),
    [
        ("what do you know about me?", "self"),
        ("what's my job?", "profile"),
        ("should I ask for a promotion?", "profile"),
        ("what should I cook tonight?", "query"),
    ],
)
async def test_personal_turns_pick_how_much_memory_to_read(text, scope):
    plan = await _plan(text, advice=True)
    assert plan.memory_scope == scope


async def _system_prompt(text: str, *, memory: bool = True, status: str = "ok", block: str = ""):
    user = _user(memory=memory)
    chat = Chat(id=uuid4(), user_id=user.id, title=None)

    async def blocks(*_args, **_kwargs):
        return _PromptContextBlocks(
            memory_block=block,
            todos_section=None,
            recent_all=[],
            attachment_rag_block="",
            chat=chat,
            memory_status=status,
        )

    with (
        patch("app.modules.chat.prompt_builder._load_context_blocks", blocks),
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=False)),
    ):
        messages = await build_prompt_messages(
            user,
            chat.id,
            Settings(chat_history_rag_enabled=False, attachment_rag_enabled=False),
            chat=chat,
            query_text=text,
            rich_context=False,
            advice_memory=True,
        )
    return "\n\n".join(m["content"] for m in messages if m["role"] == "system")


@pytest.mark.asyncio
async def test_a_failed_memory_read_is_said_not_denied():
    """M17: a profile ask with memory unavailable never says "I don't have that"."""
    system = await _system_prompt("what's my second language?", status="unavailable")
    assert prompt_memory.MEMORY_UNAVAILABLE_HINT in system
    assert PROFILE_FACT_HINT not in system

    ok = await _system_prompt(
        "what's my second language?", block="Known facts about the user:\n- Speaks Amharic"
    )
    assert PROFILE_FACT_HINT in ok
    assert prompt_memory.MEMORY_UNAVAILABLE_HINT not in ok


@pytest.mark.asyncio
async def test_a_partial_read_is_said_only_when_asked_what_is_saved():
    asked = await _system_prompt("what's my job?", status="partial")
    assert prompt_memory.MEMORY_PARTIAL_HINT in asked
    advice = await _system_prompt("what should I cook tonight?", status="partial")
    assert prompt_memory.MEMORY_PARTIAL_HINT not in advice


@pytest.mark.asyncio
async def test_remember_with_memory_off_says_so():
    """M8: memory off + "remember that I'm vegetarian" → the reply can't promise it."""
    system = await _system_prompt("remember that I'm vegetarian", memory=False)
    assert prompt_memory.MEMORY_OFF_HINT in system
    plain = await _system_prompt("what should I cook tonight?", memory=False)
    assert prompt_memory.MEMORY_OFF_HINT not in plain


@pytest.mark.asyncio
async def test_remember_while_saving_is_paused_says_so():
    user = _user()
    chat = Chat(id=uuid4(), user_id=user.id, title=None)

    async def blocks(*_args, **_kwargs):
        return _PromptContextBlocks("", None, [], "", chat)

    with (
        patch("app.modules.chat.prompt_builder._load_context_blocks", blocks),
        patch("app.services.quota.global_spend_exceeded", AsyncMock(return_value=True)),
    ):
        messages = await build_prompt_messages(
            user, chat.id, Settings(), chat=chat, query_text="remember that I'm vegetarian"
        )
    assert prompt_memory.MEMORY_PAUSED_HINT in system_prompt(messages)


@pytest.mark.asyncio
async def test_a_recalled_past_with_no_record_is_not_invented():
    """M16: "what did we decide last time" with no earlier chat found."""
    system = await _system_prompt("What did we decide about the database last time?")
    assert prompt_memory.NO_PAST_RECORD_HINT in system
    other = await _system_prompt("what should I cook tonight?")
    assert prompt_memory.NO_PAST_RECORD_HINT not in other
    # The news last week is not a conversation the user had with Recall.
    news = await _system_prompt("what happened in the news last week?")
    assert prompt_memory.NO_PAST_RECORD_HINT not in news


def test_the_saved_memory_block_says_it_may_be_stale():
    """M4/M9/M21: dated, overridden by this conversation, not a source for code state."""
    from app.services.prompt_safety import wrap_earlier_chats, wrap_saved_memory

    memory = wrap_saved_memory("Known facts about the user:\n- Uses FastAPI")
    assert memory.startswith("[BEGIN UNTRUSTED CONTENT — saved memory]")
    assert "what the user says in this conversation overrides it" in memory  # safety phrase
    assert "comes from the current source" in memory  # safety phrase
    chats = wrap_earlier_chats("[1] (2026-05-03) User: we picked Neon")
    assert "not this conversation and not saved memory" in chats  # safety phrase


@pytest.mark.parametrize(
    ("text", "work"),
    [
        ("How should I structure auth in my app?", True),
        ("fix the bug in our backend", True),
        ("what is recursion", True),
        ("find the derivative of the function f(x) = x^2 + 3x", False),
        ("write a python function that reverses a list", True),
        ("my history project is due friday, any tips?", True),
        ("plan my weekend", False),
        ("what's a good name for a cat", False),
        ("a key component of happiness", False),
    ],
)
def test_work_turns_are_about_building_software(text, work):
    assert prompt_memory.is_work_turn(text) is work


def test_memory_switch_counts_an_unloaded_row_as_on():
    assert memory_switch_on(cast(User, SimpleNamespace(memory_enabled=None)))
    assert not memory_switch_on(cast(User, SimpleNamespace(memory_enabled=False)))
    assert memory_switch_on(None)


@pytest.mark.asyncio
async def test_asking_which_option_i_picked_reads_memory_and_earlier_chats():
    """M16: "which option did I pick?" recalls a decision from an earlier chat."""
    assert prompt_memory.recalls_shared_past("which option did I pick for the database?")
    assert not prompt_memory.recalls_shared_past("did it rain in Paris yesterday?")
    plan = await _plan("which option did I pick for the database?")
    assert plan.load_memory is True
    assert plan.history_rag is True
