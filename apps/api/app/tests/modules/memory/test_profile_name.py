"""The profile name is the user's name: a saved fact naming them otherwise stays out."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.memory.facts import identity_core, render_memory_block
from app.modules.memory.name_claim import as_chosen_name, stated_user_names
from app.modules.memory.pass_writes import writes_from_ops
from app.modules.memory.profile_name import names_another_person, without_conflicting_names
from app.modules.memory.schemas import MemoryFactOp

_SAID = datetime(2026, 10, 24, tzinfo=UTC)
# The live account: profile name Dev, an older test fact naming the user Sam.
_SAM = "User's name is Sam; they are a nursing student living in Chicago"


def _fact(text: str, kind: str = "profile", said: datetime = _SAID) -> SimpleNamespace:
    return SimpleNamespace(
        type=kind, text=text, last_confirmed_at=said, created_at=said, confidence=1.0
    )


def _block(*texts: str) -> str:
    return render_memory_block(
        [_fact(text) for text in texts] + [_fact("User prefers dark mode", "preference")]
    )


@pytest.mark.parametrize(
    ("fact", "profile_name"),
    [
        (_SAM, "Dev"),
        ("The user's name is Sam", "Dev Patel"),
        ("Sam is the user's name", "Dev"),
        ("The user is Sam", "Dev"),
        ("User is named Sam", "Dev"),
        # A stated name with a nickname is still a stated name.
        ("User's name is Sam; also goes by Sammy", "Dev"),
    ],
)
def test_a_fact_naming_someone_else_is_another_person(fact: str, profile_name: str) -> None:
    assert names_another_person(fact, profile_name)


@pytest.mark.parametrize(
    ("fact", "profile_name"),
    [
        ("User's name is Dev", "Dev"),
        ("User's name is dev", "Dev Patel"),
        ("User's name is Patel", "Dev Patel"),
        # A short form of the profile name is the same person.
        ("User's name is Bini", "Binalfew Mecuriaw"),
        ("User's name is Sam", "Samantha"),
        ("User's name is Al", "Alan"),
        # The name they chose to be called stays beside the profile name.
        ("User goes by Sam", "Dev"),
        ("User's name is Dev; also goes by Sam", "Dev"),
        # Not a name for the user at all.
        ("User is a nursing student", "Dev"),
        ("User's dog is named Sam", "Dev"),
        ("User's sister's name is Sam", "Dev"),
        # No profile name: memory is the only source of the name.
        (_SAM, None),
        (_SAM, ""),
        (_SAM, "  "),
    ],
)
def test_facts_that_agree_or_name_no_one_stay(fact: str, profile_name: str | None) -> None:
    assert not names_another_person(fact, profile_name)


def test_the_block_drops_the_line_naming_someone_else() -> None:
    block = _block(_SAM)

    filtered = without_conflicting_names(block, "Dev")

    assert "Sam" not in filtered
    assert "## Profile" not in filtered
    assert "User prefers dark mode" in filtered
    assert filtered == render_memory_block([_fact("User prefers dark mode", "preference")])


def test_the_block_keeps_other_profile_lines() -> None:
    block = _block(_SAM, "User is from Ethiopia")

    filtered = without_conflicting_names(block, "Dev")

    assert "Sam" not in filtered
    assert "User is from Ethiopia" in filtered
    assert "## Profile" in filtered


def test_a_block_of_only_the_conflicting_name_is_empty() -> None:
    assert without_conflicting_names(render_memory_block([_fact(_SAM)]), "Dev") == ""


@pytest.mark.parametrize("profile_name", ["Sam", "Samuel Lee", None])
def test_the_block_is_unchanged_when_nothing_conflicts(profile_name: str | None) -> None:
    block = _block(_SAM)
    assert without_conflicting_names(block, profile_name) == block


def test_a_name_in_another_section_is_left_alone() -> None:
    block = render_memory_block([_fact("User's name is Sam", "fact")])
    assert without_conflicting_names(block, "Dev") == block


def test_a_mock_profile_name_reads_as_none() -> None:
    block = _block(_SAM)
    assert without_conflicting_names(block, AsyncMock()) == block


@pytest.mark.asyncio
async def test_every_prompt_reads_the_block_without_the_other_name(fake_redis) -> None:
    from app.modules.memory import get_memory_block

    user = User(id=uuid4(), email="dev@example.com", name="Dev", memory_enabled=True)
    rows = [
        SimpleNamespace(
            id=uuid4(),
            type=kind,
            text=text,
            status="active",
            confidence=1.0,
            importance=0.8,
            sensitivity="normal",
            topic=None,
            last_confirmed_at=_SAID,
            created_at=_SAID,
        )
        for kind, text in (("profile", _SAM), ("preference", "User prefers dark mode"))
    ]
    with patch("app.modules.memory.repository.list_for_user", AsyncMock(return_value=rows)):
        block = await get_memory_block(
            AsyncMock(), user, Settings(semantic_memory_enabled=False), scope="self"
        )
        # A renamed profile takes effect on the cached block too.
        user.name = "Sam"
        renamed = await get_memory_block(
            AsyncMock(), user, Settings(semantic_memory_enabled=False), scope="self"
        )

    assert "Sam" not in block
    assert "User prefers dark mode" in block
    assert _SAM in renamed


@pytest.mark.parametrize(
    ("text", "speech", "saved"),
    [
        ("User's name is Sam", "User: call me Sam", "User goes by Sam"),
        ("The user's name is Sam.", "User: Please call me Sam from now on!", "User goes by Sam"),
        ("User's name is Sam", "User: I go by Sam", "User goes by Sam"),
        ("User is named Sam", "User: I'd like to be called Sam", "User goes by Sam"),
        # Who they are, said in their own words, stays their name.
        ("User's name is Sam", "User: my name is Sam", "User's name is Sam"),
        ("User's name is Sam", "User: I'm Sam. Call me Sam.", "User's name is Sam"),
        # More than the name, or a name they never asked for: unchanged.
        (_SAM, "User: call me Sam", _SAM),
        ("User's name is Sam", "User: call me Ben", "User's name is Sam"),
        ("User works at Stripe", "User: call me Sam", "User works at Stripe"),
    ],
)
def test_call_me_saves_the_name_they_chose(text: str, speech: str, saved: str) -> None:
    assert as_chosen_name(text, speech) == saved


def test_call_me_is_written_as_a_nickname() -> None:
    op = MemoryFactOp(
        op="add", type="profile", text="User's name is Sam", confidence=0.9, importance=0.8
    )

    writes, skipped = writes_from_ops(
        [op],
        chat_id=uuid4(),
        explicit_remember=False,
        include_sensitive=False,
        min_confidence=0.5,
        transcript="User: call me Sam",
    )

    assert skipped == 0
    assert [write.text for write in writes] == ["User goes by Sam"]
    assert not names_another_person(writes[0].text, "Dev")


def test_stated_names_leave_out_nicknames() -> None:
    assert stated_user_names("User's name is Dev; also goes by Sam") == ["dev"]
    assert stated_user_names("User goes by Sam") == []


def test_the_newest_name_is_the_one_in_every_prompt() -> None:
    older = _fact("User's name is Bini", said=datetime(2026, 1, 5, tzinfo=UTC))
    older_but_important = _fact("User goes by B", said=datetime(2026, 2, 5, tzinfo=UTC))
    older_but_important.importance = 1.0
    newest = _fact("User goes by Ben", said=datetime(2026, 9, 1, tzinfo=UTC))
    newest.importance = 0.5

    core = identity_core([older, older_but_important, newest])  # type: ignore[list-item]

    assert [memory.text for memory in core] == ["User goes by Ben"]
