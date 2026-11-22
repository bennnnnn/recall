"""Which turns read memory, and what the prompt says about it (live QA, 2026-11-22)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat.prompt_builder import _context_plan
from app.modules.chat.turn_prep.mode import classify_turn_mode


async def _plan(question: str):
    mode = classify_turn_mode([], question)
    return await _context_plan(
        SimpleNamespace(id=uuid4(), memory_enabled=True),  # type: ignore[arg-type]
        uuid4(),
        Settings(),
        query_text=question,
        minimal_personal_context=mode.minimal_personal,
        lightweight=mode.lightweight,
        rich_context=mode.rich_context,
        advice_memory=mode.advice_memory,
        probe_attachment_rag=False,
    )


@pytest.mark.parametrize(
    "question",
    [
        "what job do i do again",
        "what car do i have",
        "any gift ideas for my family?",
        "what should i cook tonight",
        "what do u know about me",
    ],
)
async def test_a_turn_about_anything_reads_memory(question):
    plan = await _plan(question)
    assert plan.load_memory


@pytest.mark.parametrize("question", ["what job do i do again", "what car do i have"])
async def test_a_turn_no_word_rule_knows_reads_without_a_query_embed(question):
    plan = await _plan(question)
    assert plan.memory_scope == "ambient"


@pytest.mark.parametrize("question", ["thanks", "ok", "lol"])
async def test_a_greeting_or_an_ack_reads_none(question):
    plan = await _plan(question)
    assert not plan.load_memory


async def test_memory_off_reads_none():
    mode = classify_turn_mode([], "what job do i do again")
    plan = await _context_plan(
        SimpleNamespace(id=uuid4(), memory_enabled=False),
        uuid4(),
        Settings(),
        query_text="what job do i do again",
        minimal_personal_context=mode.minimal_personal,
        lightweight=mode.lightweight,
        rich_context=mode.rich_context,
        advice_memory=mode.advice_memory,
        probe_attachment_rag=False,
    )
    assert not plan.load_memory


async def test_a_whole_store_block_is_not_cut_to_the_slim_budget(fake_redis):
    from unittest.mock import AsyncMock, patch

    from app.modules.chat.prompt_context import _load_context_blocks
    from app.tests.modules.memory.test_whole_store_recall import _fact

    rows = [_fact(f"User has a long saved fact about thing number {n} here") for n in range(14)]
    user = SimpleNamespace(id=uuid4(), name=None, memory_enabled=True)
    with patch("app.modules.memory.repository.list_for_user", AsyncMock(return_value=rows)):
        blocks = await _load_context_blocks(
            user,
            uuid4(),
            Settings(),
            chat=None,
            query_text="what car do i have",
            recent_limit=20,
            slim_context=True,
            client_timezone=None,
            load_memory=True,
            recent_messages=[],
        )
    assert len(blocks.memory_block) > 1000
    assert all(row.text in blocks.memory_block for row in rows)
