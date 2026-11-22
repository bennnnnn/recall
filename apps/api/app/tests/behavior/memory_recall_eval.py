"""Measure what a new chat reads from memory: which saved facts reach the prompt, and the reply.

A script, not a test: it embeds with the real embedding model (and, with ``--reply``, asks the
everyday model), so it needs an OpenRouter key in the environment and nothing else (no
database: the saved facts and Redis are in memory).

    python -m app.tests.behavior.memory_recall_eval
    python -m app.tests.behavior.memory_recall_eval --large --reply --show

The scenario is the live QA's (2026-11-22): in an earlier chat the user told three of
``FACTS`` in passing; a new chat asks one of ``QUESTIONS``. Each store is three facts drawn
with a fixed seed. The prompt's memory is built the way a turn builds it: the turn's mode
(``turn_prep.mode``), the context plan (``prompt_builder._context_plan``: whether memory
loads and its scope) and the context blocks (``prompt_context._load_context_blocks``: the
scope's selection, the private-fact filter, the slim cap), with the saved facts, their
vectors and the cache patched in.

- Coverage: of the facts a question needs that the store holds, the share in the prompt.
  "what do you know about me" needs every fact.
- ``--large``: each store also holds ``FILLER`` (25 unrelated facts), past the size read
  whole, so the question's similarity picks the facts.
- ``--reply``: the everyday model answers from a short system prompt (the privacy rules,
  the turn's memory hint and the block); a reply uses a fact when it says one of its
  words, and one that says it found nothing while a fact answers is counted too.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import random
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

# key: (fact text, type, topic, sensitivity, words a reply uses it by, English or Spanish)
FACTS: dict[str, tuple[str, str, str, str, tuple[str, ...]]] = {
    "dog": ("User has a dog named Biscuit", "fact", "notes", "normal", ("biscuit",)),
    "veg": ("User is vegetarian", "fact", "notes", "normal", ("vegetarian", "veggie", "meat")),
    "nurse": ("User works as a nurse", "profile", "profile", "normal", ("nurse", "enfermer")),
    "denver": ("User lives in Denver", "profile", "profile", "normal", ("denver",)),
    "hana": (
        "User's sister Hana is getting married in June",
        "fact",
        "notes",
        "relationship",
        ("hana", "wedding", "sister"),
    ),
    "peanut": (
        "User is allergic to peanuts",
        "fact",
        "notes",
        "health",
        ("peanut", "nut", "cacahuete", "maní", "mani"),
    ),
    "japanese": (
        "User is learning Japanese",
        "focus",
        "goals",
        "normal",
        ("japan", "japon", "japón"),
    ),
    "civic": (
        "User drives a 2015 Honda Civic",
        "fact",
        "notes",
        "normal",
        ("civic", "honda", "carro", "coche"),
    ),
    "son": ("User has a 7-year-old son", "fact", "notes", "normal", ("son", "7", "hijo")),
}
ALL = tuple(FACTS)
# (question, kind, the facts it needs)
QUESTIONS: list[tuple[str, str, tuple[str, ...]]] = [
    ("what do u know about me", "self", ALL),
    ("what do you remember about me?", "self", ALL),
    ("tell me everything you know about me", "self", ALL),
    ("¿qué sabes de mí?", "self", ALL),
    ("what should i cook tonight", "cook", ("veg", "peanut")),
    ("any dinner ideas?", "cook", ("veg", "peanut")),
    ("any gift ideas for my family?", "gift", ("hana", "son")),
    ("what should i get my sister?", "gift", ("hana",)),
    ("remind me whats my dogs name", "pet", ("dog",)),
    ("whats my dog called again", "pet", ("dog",)),
    ("what job do i do again", "job", ("nurse", "enfermer")),
    ("where do i live again?", "home", ("denver",)),
    ("what car do i have", "car", ("civic",)),
]
FILLER = [
    "User uses VS Code with the Vim extension",
    "User plays chess online on weekends",
    "User prefers window seats on flights",
    "User follows Formula 1",
    "User is reading Dune",
    "User likes hiking in the mountains",
    "User wants to visit Iceland",
    "User plays the guitar",
    "User watches anime",
    "User uses an iPhone 15",
    "User listens to jazz while working",
    "User runs three times a week",
    "User builds a budgeting app in React Native",
    "User's backend uses FastAPI and Postgres",
    "User takes photos with a Fujifilm camera",
    "User likes board games",
    "User is saving for a house",
    "User is learning to swim",
    "User prefers emails over phone calls",
    "User uses Notion for notes",
    "User grows tomatoes on the balcony",
    "User follows the NBA",
    "User studied economics at university",
    "User likes sci-fi films",
    "User does yoga on Sundays",
]
_STORES = 40
_SEED = 22
_CONCURRENCY = 6
_FOUND_NOTHING = re.compile(
    r"\b(?:couldn'?t find|could not find|don'?t have|do not have|no (?:record|details|info))\b",
    re.IGNORECASE,
)


def _row(text: str, type_: str, topic: str, sensitivity: str) -> SimpleNamespace:
    said = datetime(2026, 11, 22, tzinfo=UTC)
    return SimpleNamespace(
        id=uuid.uuid4(),
        text=text,
        type=type_,
        topic=topic,
        sensitivity=sensitivity,
        confidence=1.0,
        status="active",
        importance=0.5,
        slot=None,
        created_at=said,
        updated_at=said,
        last_confirmed_at=said,
    )


def stores(count: int = _STORES) -> list[tuple[str, ...]]:
    pick = random.Random(_SEED)  # noqa: S311 - a fixed sample of stores, not a secret
    return [tuple(pick.sample(ALL, 3)) for _ in range(count)]


@dataclass
class Tally:
    needed: int = 0
    reached: int = 0
    used: int = 0
    said_nothing: int = 0
    cases: int = 0


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0


async def _vectors(settings: Any, texts: list[str]) -> dict[str, list[float]]:
    from app.gateways import embedding_gateway

    unique = sorted(set(texts))
    found = await embedding_gateway.embed_many(settings, unique, concurrency=8)
    return {text: vec for text, vec in zip(unique, found, strict=True) if vec}


async def prompt_memory(
    settings: Any, question: str, rows: list[Any], vectors: dict[str, list[float]]
) -> tuple[str, Any]:
    """The memory block a turn's prompt carries for ``question``, and the turn's mode."""
    import fakeredis

    from app.modules.chat.prompt_builder import _context_plan
    from app.modules.chat.prompt_context import _load_context_blocks
    from app.modules.chat.turn_prep.mode import classify_turn_mode

    mode = classify_turn_mode([], question)
    user = SimpleNamespace(id=uuid.uuid4(), name=None, memory_enabled=True, timezone="UTC")
    chat_id = uuid.uuid4()
    plan = await _context_plan(
        user,  # type: ignore[arg-type]
        chat_id,
        settings,
        query_text=question,
        minimal_personal_context=mode.minimal_personal,
        lightweight=mode.lightweight,
        rich_context=mode.rich_context,
        advice_memory=mode.advice_memory,
        probe_attachment_rag=False,
    )
    query_vec = vectors.get(question)
    scored = [
        (row, _cosine(query_vec, vectors[row.text]) if query_vec and row.text in vectors else None)
        for row in rows
    ]
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with (
        patch("app.modules.memory.retrieval.get_redis_client", return_value=redis),
        patch("app.modules.memory.cache.get_redis_client", return_value=redis),
        patch("app.modules.memory.repository.list_for_user", AsyncMock(return_value=rows)),
        patch("app.modules.memory.repository.list_scored_for_user", AsyncMock(return_value=scored)),
        patch(
            "app.gateways.embedding_gateway.get_or_embed_query",
            AsyncMock(return_value=query_vec),
        ),
        patch("app.core.background_tasks.create_background_task", side_effect=_closed),
        patch("app.modules.todos.build_todos_system_section", AsyncMock(return_value=None)),
    ):
        blocks = await _load_context_blocks(
            user,  # type: ignore[arg-type]
            chat_id,
            settings.model_copy(update={"attachment_rag_enabled": False}),
            chat=SimpleNamespace(id=chat_id),  # type: ignore[arg-type]
            query_text=question,
            recent_limit=settings.recent_message_window,
            slim_context=plan.slim,
            client_timezone=None,
            load_memory=plan.load_memory,
            memory_scope=plan.memory_scope,
            history_rag=False,
            recent_messages=[],
        )
    await redis.aclose()
    return blocks.memory_block, mode


def _closed(coro: Any, **_kwargs: Any) -> Any:
    coro.close()
    return SimpleNamespace(add_done_callback=lambda _callback: None)


async def _reply(settings: Any, question: str, block: str, mode: Any) -> str:
    from app.gateways import litellm_gateway
    from app.models.routing_lanes import ROUTING
    from app.modules.chat.prompt_constants import privacy
    from app.services.prompt_safety import wrap_saved_memory

    parts = [privacy.PRIVACY_HINT, privacy.CLARIFICATION_HINT]
    if mode.minimal_personal:
        parts.append(privacy.BROAD_SELF_ANSWER_HINT)
    elif mode.advice_memory:
        parts.append(privacy.ADVICE_PERSONALIZE_HINT)
    if block:
        parts.append(wrap_saved_memory(block))
    messages = [
        {"role": "system", "content": "\n\n".join(parts)},
        {"role": "user", "content": question},
    ]
    text = await litellm_gateway.complete_text(
        settings=settings, model_alias=ROUTING.everyday, messages=messages, max_tokens=600
    )
    return text or ""


def _uses(reply: str, key: str) -> bool:
    folded = reply.casefold()
    return any(re.search(rf"\b{re.escape(word)}", folded) for word in FACTS[key][4])


async def run(*, large: bool, reply: bool, show: bool) -> dict[str, Tally]:
    from app.core.config import Settings

    settings = Settings()
    texts = [fact[0] for fact in FACTS.values()] + [q for q, _, _ in QUESTIONS]
    vectors = await _vectors(settings, texts + (FILLER if large else []))
    filler = [_row(text, "fact", "notes", "normal") for text in FILLER] if large else []
    tallies: dict[str, Tally] = defaultdict(Tally)
    gate = asyncio.Semaphore(_CONCURRENCY)
    # The patches are global: one prompt is built at a time, the replies overlap.
    building = asyncio.Lock()

    async def one(store: tuple[str, ...], question: str, kind: str, needs: tuple[str, ...]):
        rows = [_row(*FACTS[key][:4]) for key in store] + filler
        async with building:
            block, mode = await prompt_memory(settings, question, rows, vectors)
        wanted = [key for key in needs if key in store]
        reached = [key for key in wanted if FACTS[key][0] in block]
        answer = ""
        if reply:
            async with gate:
                answer = await _reply(settings, question, block, mode)
        return kind, question, store, wanted, reached, answer

    jobs = [one(store, *question) for store in stores() for question in QUESTIONS]
    for kind, question, store, wanted, reached, answer in await asyncio.gather(*jobs):
        tally = tallies[kind]
        tally.cases += 1
        tally.needed += len(wanted)
        tally.reached += len(reached)
        if reply:
            used = [key for key in wanted if _uses(answer, key)]
            tally.used += len(used)
            nothing = bool(wanted) and bool(_FOUND_NOTHING.search(answer)) and not used
            tally.said_nothing += nothing
        if show and (len(reached) < len(wanted) or (reply and wanted and not used)):
            missing = [key for key in wanted if key not in reached]
            print(f"  {kind:5} {question!r} store={store} not in prompt={missing}")
            if reply:
                print(f"        reply: {answer[:220]!r}")
    return tallies


def report(tallies: dict[str, Tally], *, reply: bool) -> None:
    total = Tally()
    for kind, tally in sorted(tallies.items()):
        line = f"{kind:5} prompt {tally.reached}/{tally.needed}"
        if reply:
            line += f", reply used {tally.used}/{tally.needed}, said it found nothing "
            line += f"{tally.said_nothing}/{tally.cases}"
        print(line)
        for name in ("needed", "reached", "used", "said_nothing", "cases"):
            setattr(total, name, getattr(total, name) + getattr(tally, name))
    share = total.reached / total.needed if total.needed else 1.0
    print(f"all   prompt {total.reached}/{total.needed} ({share:.0%})", end="")
    if reply:
        print(f", reply used {total.used}/{total.needed} ({total.used / total.needed:.0%})")
    else:
        print()


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--large", action="store_true", help="add 25 unrelated facts a store")
    parser.add_argument("--reply", action="store_true", help="ask the everyday model too")
    parser.add_argument("--show", action="store_true", help="list the misses")
    args = parser.parse_args()
    tallies = await run(large=args.large, reply=args.reply, show=args.show)
    report(tallies, reply=args.reply)


if __name__ == "__main__":
    asyncio.run(main())
