"""A small store is read whole: the question needs no word or vector in common with the fact.

Live QA (2026-11-22), a new user with three saved facts: "any gift ideas for my family?"
got none of them (son, sister's wedding: similarity under the gate), "what do u know about
me" left out the peanut allergy (a private fact, filtered by words), and "what job do i do
again" read no memory at all.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.memory import MemoryLoadReport, get_memory_block
from app.modules.memory.facts import render_memory_block
from app.modules.memory.selection import select_whole_store


def _fact(text: str, *, type_: str = "fact", sensitivity: str = "normal") -> SimpleNamespace:
    said = datetime(2026, 11, 22, tzinfo=UTC)
    return SimpleNamespace(
        id=uuid4(),
        text=text,
        type=type_,
        topic="notes",
        sensitivity=sensitivity,
        confidence=1.0,
        status="active",
        importance=0.5,
        slot=None,
        created_at=said,
        updated_at=said,
        last_confirmed_at=said,
    )


def _store() -> list[SimpleNamespace]:
    return [
        _fact("User works as a nurse", type_="profile"),
        _fact("User has a 7-year-old son"),
        _fact("User's sister Hana is getting married in June", sensitivity="relationship"),
        _fact("User is allergic to peanuts", sensitivity="health"),
    ]


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), name=None, memory_enabled=True)


def test_a_small_store_is_selected_whole_private_facts_included():
    picked = select_whole_store(_store(), Settings(memory_min_confidence=0.0))
    assert picked is not None
    assert {fact.text for fact in picked} == {fact.text for fact in _store()}


@pytest.mark.parametrize(
    "settings",
    [
        Settings(memory_whole_store_max_facts=3),
        Settings(memory_whole_store_max_facts=0),
        Settings(memory_inject_max_chars=60),
    ],
)
def test_a_store_past_the_size_is_not_read_whole(settings):
    assert select_whole_store(_store(), settings) is None


def test_a_private_fact_is_marked_in_the_block():
    block = render_memory_block(_store())
    assert "- User is allergic to peanuts (said 2026-11, private)" in block
    assert "- User has a 7-year-old son (said 2026-11)" in block


@pytest.mark.parametrize(
    ("question", "scope"),
    [
        ("any gift ideas for my family?", "query"),
        ("what job do i do again", "query"),
        ("what do u know about me", "self"),
    ],
)
async def test_every_scope_but_work_reads_a_small_store_whole(fake_redis, question, scope):
    embed = AsyncMock(return_value=[1.0, 0.0])
    report = MemoryLoadReport()
    with (
        patch("app.modules.memory.repository.list_for_user", AsyncMock(return_value=_store())),
        patch("app.gateways.embedding_gateway.get_or_embed_query", embed),
    ):
        block = await get_memory_block(
            AsyncMock(),
            _user(),
            Settings(),
            query_text=question,
            exclude_sensitive=True,
            scope=scope,
            report=report,
        )

    for fact in _store():
        assert fact.text in block
    embed.assert_not_awaited()
    assert report.whole_store and report.status == "ok"


async def test_a_large_store_still_reads_by_the_question(fake_redis):
    store = _store() + [_fact(f"User likes hobby number {n}") for n in range(20)]
    scored = [(fact, 0.9 if "nurse" in fact.text else 0.0) for fact in store]
    with (
        patch("app.modules.memory.repository.list_for_user", AsyncMock(return_value=store)),
        patch("app.modules.memory.repository.list_scored_for_user", AsyncMock(return_value=scored)),
        patch(
            "app.gateways.embedding_gateway.get_or_embed_query",
            AsyncMock(return_value=[1.0, 0.0]),
        ),
    ):
        block = await get_memory_block(
            AsyncMock(), _user(), Settings(), query_text="what job do i do again"
        )

    assert "User works as a nurse" in block
    assert "hobby number" not in block


async def test_what_do_you_know_about_me_keeps_private_facts_in_a_large_store(fake_redis):
    store = _store() + [_fact(f"User likes hobby number {n}") for n in range(12)]
    with patch("app.modules.memory.repository.list_for_user", AsyncMock(return_value=store)):
        block = await get_memory_block(
            AsyncMock(),
            _user(),
            Settings(),
            query_text="what do u know about me",
            exclude_sensitive=True,
            scope="self",
        )

    assert "User is allergic to peanuts" in block


async def test_the_whole_store_block_is_cached_until_memory_changes(fake_redis):
    from app.modules.memory import invalidate_memory_block

    user = _user()
    rows = AsyncMock(return_value=_store())
    with patch("app.modules.memory.repository.list_for_user", rows):
        first = await get_memory_block(AsyncMock(), user, Settings(), query_text="hi there")
        second = await get_memory_block(AsyncMock(), user, Settings(), query_text="other")
        assert first == second
        assert rows.await_count == 1
        await invalidate_memory_block(user.id)
        await get_memory_block(AsyncMock(), user, Settings(), query_text="other")
    assert rows.await_count == 2


async def test_a_failed_read_is_unavailable_not_an_empty_memory(fake_redis):
    report = MemoryLoadReport()
    with patch(
        "app.modules.memory.repository.list_for_user",
        AsyncMock(side_effect=RuntimeError("db down")),
    ):
        block = await get_memory_block(
            AsyncMock(), _user(), Settings(), query_text="what job do i do", report=report
        )
    assert block == ""
    assert report.status == "unavailable"


async def test_a_turn_that_names_nothing_reads_who_the_user_is_of_a_large_store(fake_redis):
    """The ambient scope embeds nothing: a large store gives the profile document."""
    store = _store() + [_fact(f"User likes hobby number {n}") for n in range(20)]
    embed = AsyncMock(return_value=[1.0, 0.0])
    with (
        patch("app.modules.memory.repository.list_for_user", AsyncMock(return_value=store)),
        patch("app.gateways.embedding_gateway.get_or_embed_query", embed),
    ):
        block = await get_memory_block(
            AsyncMock(), _user(), Settings(), query_text="what job do i do again", scope="ambient"
        )

    assert "User works as a nurse" in block
    assert "hobby number" not in block
    embed.assert_not_awaited()
