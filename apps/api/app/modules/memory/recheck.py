"""Read one user's saved facts again under today's extraction rules; mute what fails.

Facts saved before the rules held each one to the user's own words (``grounding``) stay
active until something reads them again. This reads every active fact's source chat, asks
the memory model to quote the words that state it and say how they were said, and applies
the same server checks a live pass does. A fact that passes stays (with its source message
and slot); one that fails is muted, which Settings → Memory can undo. Nothing is deleted.

    python -m app.modules.memory.recheck --email someone@example.com          # dry run
    python -m app.modules.memory.recheck --email someone@example.com --apply

A lesson line (the lesson job's) and a fact with no source chat (written by hand, or its
chat deleted) are kept as they are: there is nothing to read them against. Among the facts
kept, an older answer in the same slot and an older fact a newer one says again in other
words are muted too.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways import litellm_gateway
from app.models.orm import Chat, Memory, Message, User
from app.models.routing_lanes import ROUTING
from app.modules.memory.cache import invalidate_memory_block
from app.modules.memory.commands import is_explicit_memory_command
from app.modules.memory.extract_backlog import format_context, source_lines
from app.modules.memory.fact_quality import is_learning_line
from app.modules.memory.grounding import SourceLine, ground_fact, quoted_line
from app.modules.memory.llm import STATED_RULES
from app.modules.memory.ops import ACTIVE_STATUS, MUTED_STATUS
from app.modules.memory.schemas import memory_slot
from app.services.prompt_safety import wrap_untrusted

# The chat read for a fact: its messages up to a little after the fact was last confirmed.
_CHAT_MESSAGES = 40
_AFTER_CONFIRMED = timedelta(minutes=2)
# A later confirmation can point a fact at another chat, or move its chat window past the
# line that first said it; the lines the user wrote around the time it was first saved,
# in any chat, are read too.
_AROUND_CREATED = timedelta(minutes=10)
# Reads of each chat; a fact must pass every one.
_READS = 2
# Facts read in one call.
_BATCH = 20


@dataclass(frozen=True)
class SavedFact:
    id: UUID
    text: str
    created_at: datetime
    confirmed_at: datetime
    source_chat_id: UUID | None


@dataclass(frozen=True)
class Verdict:
    fact: SavedFact
    keep: bool
    reason: str
    source_message_id: UUID | None = None
    slot: str | None = None
    # Read against its chat and found stated; lesson lines, hand edits and facts with no
    # chat are kept as they are and never muted for another fact either.
    read: bool = False


@dataclass
class _Evidence:
    """What one source chat's facts are read against."""

    transcript: str
    lines: list[SourceLine] = field(default_factory=list)


class _Reading(BaseModel):
    fact: int
    quote: str | None = None
    stated_as: str | None = None
    slot: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _clean(cls, data: object) -> object:
        if isinstance(data, dict):
            return {**data, "slot": memory_slot(data.get("slot"))}
        return data


class _Readings(BaseModel):
    conversation: str | None = None
    facts: list[_Reading] = Field(default_factory=list)


_SHAPE = (
    '{"conversation": "real_life|story", "facts": [{"fact": 1, "quote": "the user\'s '
    'words that state it, copied exactly from one User line, else omit", "stated_as": '
    '"own_life|story|question|request|someone_else", "slot": "else omit"}]}'
)


def _messages(facts: Sequence[SavedFact], evidence: _Evidence) -> list[dict[str, str]]:
    numbered = "\n".join(f"{index}. {fact.text}" for index, fact in enumerate(facts, start=1))
    return [
        {
            "role": "system",
            "content": (
                "These facts were saved about the user from the chat below. Read each one "
                "again as if it were new: quote the user's own words that state it and say "
                f"how they said them. Return ONLY JSON (no markdown): {_SHAPE} .\n\n"
                f"{STATED_RULES}\n\n"
                "- Here every User line of the chat may state a fact; the Assistant lines "
                "are context.\n"
                "- One entry per saved fact, numbered as given. A fact no User line states "
                "gets no quote."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Saved facts:\n{numbered}\n\n"
                f"{wrap_untrusted('conversation transcript', evidence.transcript)}"
            ),
        },
    ]


async def _read_again(
    settings: Settings, facts: Sequence[SavedFact], evidence: _Evidence
) -> _Readings | None:
    # A one-off pass over facts already saved: the steadier structured reader, not the
    # cheap per-turn one (whose reading of the same fact changed from run to run).
    return await litellm_gateway.complete_structured(
        settings=settings,
        model_alias=ROUTING.structured_fallback,
        messages=_messages(facts, evidence),
        schema=_Readings,
        max_tokens=2048,
        fallback_on_invalid=True,
    )


def judge(
    fact: SavedFact,
    reading: _Reading | None,
    *,
    story: bool,
    lines: Sequence[SourceLine],
    english: bool,
) -> Verdict:
    """The live pass's checks, on one saved fact and the model's reading of it."""
    if reading is None:
        # Skipped in the model's answer: unread is not refuted.
        return Verdict(fact, keep=True, reason="the model did not read it; left as it is")
    if not reading.quote:
        return Verdict(fact, keep=False, reason="no line of the user's states it")
    line = quoted_line(reading.quote, lines)
    grounding = ground_fact(
        quote=reading.quote,
        fact=fact.text,
        stated_as="story" if story else reading.stated_as,
        lines=lines,
        explicit_remember=line is not None and is_explicit_memory_command(line.text),
        english=english,
    )
    if grounding.line is None:
        return Verdict(fact, keep=False, reason=f"{grounding.reason}: {reading.quote!r}")
    return Verdict(
        fact,
        keep=True,
        reason=f"stated: {reading.quote!r}",
        source_message_id=grounding.line.message_id,
        slot=reading.slot,
        read=True,
    )


# A hand edit stamps the fact and the account together (``crud``), a moment apart.
_SAME_EDIT = timedelta(seconds=5)


def edited_by_hand(fact: SavedFact, edited_at: datetime | None) -> bool:
    """A fact last written by the user's own edit: its words are theirs, whatever the chat
    says. Only the newest hand edit is stamped on the account, so older ones are read."""
    return edited_at is not None and abs(fact.confirmed_at - edited_at) <= _SAME_EDIT


def without_older_answers(verdicts: list[Verdict]) -> list[Verdict]:
    """Of the kept facts in one slot, the newest stays; the older ones are muted."""
    newest: dict[str, Verdict] = {}
    for verdict in verdicts:
        if verdict.keep and verdict.slot:
            held = newest.get(verdict.slot)
            if held is None or verdict.fact.confirmed_at > held.fact.confirmed_at:
                newest[verdict.slot] = verdict
    return [
        Verdict(verdict.fact, keep=False, reason=f"older answer for {verdict.slot}")
        if verdict.keep and verdict.slot and newest[verdict.slot] is not verdict
        else verdict
        for verdict in verdicts
    ]


async def _load_facts(session: AsyncSession, user_id: UUID) -> list[SavedFact]:
    # Columns, not the row: a dry run reads a database the slot column may not be in yet.
    result = await session.execute(
        select(
            Memory.id,
            Memory.text,
            Memory.created_at,
            Memory.last_confirmed_at,
            Memory.source_chat_id,
        )
        .where(Memory.user_id == user_id, Memory.status == ACTIVE_STATUS)
        .order_by(Memory.created_at)
    )
    return [SavedFact(*row) for row in result.all()]


async def _evidence(
    session: AsyncSession, user_id: UUID, chat_id: UUID, facts: Sequence[SavedFact]
) -> _Evidence:
    until = max(fact.confirmed_at for fact in facts) + _AFTER_CONFIRMED
    chat = await session.execute(
        select(Message.id, Message.role, Message.content)
        .where(Message.chat_id == chat_id, Message.created_at <= until)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(_CHAT_MESSAGES)
    )
    rows = list(reversed(chat.all()))
    read = {message_id for message_id, _, _ in rows}
    nearby = [line for line in await _lines_around(session, user_id, facts) if line[0] not in read]
    transcript = format_context([(role, content) for _, role, content in rows])
    if nearby:
        others = "\n".join(f"User: {content}" for _, content in nearby)
        transcript += f"\n\nThe user's lines when these facts were first saved:\n{others}"
    lines = source_lines(
        [(message_id, content) for message_id, role, content in rows if role == "user"] + nearby
    )
    return _Evidence(transcript=transcript, lines=list(lines))


async def _lines_around(
    session: AsyncSession, user_id: UUID, facts: Sequence[SavedFact]
) -> list[tuple[UUID, str]]:
    found: dict[UUID, str] = {}
    for fact in facts:
        result = await session.execute(
            select(Message.id, Message.content)
            .join(Chat, Chat.id == Message.chat_id)
            .where(
                Chat.user_id == user_id,
                Message.role == "user",
                Message.created_at.between(
                    fact.created_at - _AROUND_CREATED, fact.created_at + _AROUND_CREATED
                ),
            )
            .order_by(Message.created_at)
        )
        found.update((message_id, content) for message_id, content in result.all())
    return list(found.items())


async def _said_again(
    session: AsyncSession, verdicts: list[Verdict], min_similarity: float
) -> list[Verdict]:
    """Of two kept facts that say the same thing in other words, the newer stays."""
    kept = {verdict.fact.id: verdict for verdict in verdicts if verdict.keep and verdict.read}
    if len(kept) < 2:
        return verdicts
    left, right = aliased(Memory), aliased(Memory)
    pairs = await session.execute(
        select(left.id, right.id).where(
            left.id.in_(kept),
            right.id.in_(kept),
            left.id < right.id,
            left.embedding.isnot(None),
            right.embedding.isnot(None),
            left.embedding.cosine_distance(right.embedding) <= 1 - min_similarity,
        )
    )
    older = older_of_pairs([(kept[one].fact, kept[other].fact) for one, other in pairs.all()])
    return [
        Verdict(verdict.fact, keep=False, reason="a newer fact says it again")
        if verdict.fact.id in older
        else verdict
        for verdict in verdicts
    ]


def older_of_pairs(pairs: list[tuple[SavedFact, SavedFact]]) -> set[UUID]:
    """The older fact of each near-duplicate pair, newest pairs first. A pair whose newer
    fact is already muted is skipped: in a chain A~B~C, A is muted only if it is near the
    fact that stays."""
    ordered = sorted(
        (sorted(pair, key=lambda fact: fact.confirmed_at) for pair in pairs),
        key=lambda pair: pair[1].confirmed_at,
        reverse=True,
    )
    muted: set[UUID] = set()
    for old, new in ordered:
        if new.id not in muted:
            muted.add(old.id)
    return muted


async def _verdicts_for_chat(
    settings: Settings,
    session: AsyncSession,
    user: User,
    chat_id: UUID,
    facts: list[SavedFact],
) -> list[Verdict]:
    """Two reads of the chat; a fact stays only when both keep it (when unsure, it is not
    the user's own life). The same fact flipped between single reads."""
    evidence = await _evidence(session, user.id, chat_id, facts)
    english = (user.locale or "en").casefold().startswith("en")
    reads = [
        _judged(facts, readings, evidence, english)
        for readings in [await _read_again(settings, facts, evidence) for _ in range(_READS)]
        if readings is not None
    ]
    if not reads:
        return [
            Verdict(fact, keep=True, reason="model gave no answer; left as it is") for fact in facts
        ]
    return [both_keep(list(verdicts)) for verdicts in zip(*reads, strict=True)]


def _judged(
    facts: list[SavedFact], readings: _Readings, evidence: _Evidence, english: bool
) -> list[Verdict]:
    by_number = {reading.fact: reading for reading in readings.facts}
    story = (readings.conversation or "").strip().casefold() == "story"
    return [
        judge(fact, by_number.get(index), story=story, lines=evidence.lines, english=english)
        for index, fact in enumerate(facts, start=1)
    ]


def both_keep(verdicts: list[Verdict]) -> Verdict:
    """One fact's verdicts from each read: the first that mutes it, else the first."""
    return next((verdict for verdict in verdicts if not verdict.keep), verdicts[0])


async def recheck_user(settings: Settings, user_id: UUID) -> list[Verdict]:
    """Every active fact of the user with its verdict; nothing is written."""
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if user is None:
            return []
        facts = await _load_facts(session, user_id)
        verdicts: list[Verdict] = []
        by_chat: dict[UUID, list[SavedFact]] = {}
        for fact in facts:
            if is_learning_line(fact.text):
                verdicts.append(Verdict(fact, keep=True, reason="lesson line (the lesson job's)"))
            elif edited_by_hand(fact, user.memory_edited_at):
                verdicts.append(Verdict(fact, keep=True, reason="written by the user's own edit"))
            elif fact.source_chat_id is None:
                verdicts.append(Verdict(fact, keep=True, reason="no source chat to read"))
            else:
                by_chat.setdefault(fact.source_chat_id, []).append(fact)
        for chat_id, chat_facts in by_chat.items():
            # A batch's answer fits the model's output room (a quote and labels each).
            for start in range(0, len(chat_facts), _BATCH):
                batch = chat_facts[start : start + _BATCH]
                verdicts.extend(await _verdicts_for_chat(settings, session, user, chat_id, batch))
        verdicts = without_older_answers(verdicts)
        return await _said_again(session, verdicts, settings.memory_near_duplicate_similarity)


async def apply_verdicts(user_id: UUID, verdicts: Sequence[Verdict]) -> None:
    """Mute what failed; point what passed at its message and slot. One transaction."""
    async with SessionLocal() as session:
        try:
            for verdict in verdicts:
                values = (
                    {"status": MUTED_STATUS}
                    if not verdict.keep
                    else {
                        key: value
                        for key, value in (
                            ("source_message_id", verdict.source_message_id),
                            ("slot", verdict.slot),
                        )
                        if value is not None
                    }
                )
                if values:
                    await session.execute(
                        update(Memory)
                        .where(Memory.id == verdict.fact.id, Memory.user_id == user_id)
                        .values(**values)
                    )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    await invalidate_memory_block(user_id)


async def _user_id(email: str | None, user_id: str | None) -> UUID:
    if user_id:
        return UUID(user_id)
    async with SessionLocal() as session:
        found = await session.scalar(select(User.id).where(User.email == email))
    if found is None:
        raise SystemExit(f"No user with email {email!r}")
    return found


async def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Re-check one user's saved memory facts.")
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--email")
    who.add_argument("--user-id")
    parser.add_argument("--apply", action="store_true", help="mute what fails (default: dry run)")
    args = parser.parse_args(argv)
    user_id = await _user_id(args.email, args.user_id)
    verdicts = await recheck_user(Settings(), user_id)
    for verdict in sorted(verdicts, key=lambda item: (not item.keep, item.fact.created_at)):
        mark = "KEEP" if verdict.keep else "MUTE"
        print(f"{mark}  {verdict.fact.text}\n      {verdict.reason}")
    kept = sum(verdict.keep for verdict in verdicts)
    print(f"\n{kept} kept, {len(verdicts) - kept} to mute{'' if args.apply else ' (dry run)'}")
    if args.apply:
        await apply_verdicts(user_id, verdicts)


if __name__ == "__main__":
    asyncio.run(main())
