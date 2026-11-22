"""Measure who decides a picture: whether a message gets a painting, a photo or a reply.

A script, not a test: it calls the real read models through the gateway, so it needs an
OpenRouter key in the environment and nothing else (no database).

    python -m app.tests.behavior.picture_ask_eval --runs 2
    python -m app.tests.behavior.picture_ask_eval --words   # the words alone, as before

Every turn of ``picture_ask_corpus.json`` is a message with the chat before it, labelled
with what it asks of images: ``image`` (a picture to paint, a change to one just painted),
``photo`` (a real thing to look up) or ``none``. The owner's chat (2026-11-22) is in it line
by line: after one painted picture, "You keep generating an image", "did i ask about an
image?" and "Man this is so bad" were each answered by another, decided by word rules. A
picture in the chat before a turn is written ``[generated: <prompt>]``, ``[photo: <query>]``
or ``[answer-photo: <query>]`` above a reply's text, and stored as the app stores it: an
``[Image: …]`` line on the reply, its label on the attachment.

It runs the turn's decision as the chat turn's intercept does (``chat.turn_intercepts``):
the words' candidates, then the turn's read; a message sent with a photo attached as the
composer does (``images.intent``). It prints precision and recall for each answer, the
false pictures on the complaints and look-alikes, and the turns it misses. Ship rule (owner,
2026-11-22): no false painting on the complaints, recall of 90% or more on the requests.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

CORPUS = Path(__file__).with_name("picture_ask_corpus.json")
_CONCURRENCY = 6
_KINDS = ("image", "photo", "none")
_SHOWN = {
    "generated": ("image-gen-model", "generated"),
    "photo": ("image-search-model", "search"),
    "answer-photo": ("free-chat", "search"),
}


def load(path: Path = CORPUS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(path.read_text())
    return rows


def stored_rows(history: list[list[str]]) -> tuple[list[SimpleNamespace], dict[uuid.UUID, Any]]:
    """The chat as the app stores it, and each picture's label as the attachment keeps it."""
    from app.modules.attachments.markers import image_marker

    rows: list[SimpleNamespace] = []
    labels: dict[uuid.UUID, Any] = {}
    for role, content in history:
        model = "free-chat" if role == "assistant" else None
        head, _, rest = content.partition("\n")
        kind, _, label = head.strip("[]").partition(": ")
        if role == "assistant" and head.startswith("[") and kind in _SHOWN:
            model, source = _SHOWN[kind]
            uid = uuid.uuid4()
            # Read as ``chat.shown_pictures.ShownPicture`` is.
            labels[uid] = SimpleNamespace(source=source, label=label)
            content = image_marker(uid) + (f"\n\n{rest}" if rest else "")
        rows.append(SimpleNamespace(id=uuid.uuid4(), role=role, content=content, model=model))
    return rows, labels


def words_alone(row: dict[str, Any]) -> str:
    """What the words decided before the read did, on main before 2026-11-22: a photo the
    lookup words found, else the picture the generation words found."""
    from app.modules.images import intent
    from app.modules.images.lookup_intent import extract_image_lookup_query

    rows, _labels = stored_rows(row["history"])
    text = row["prompt"]
    if row.get("attached"):
        found = intent.composer_image_intent(text, rows, image_attached=True)  # type: ignore[attr-defined]
        return "image" if found.request else "none"
    if extract_image_lookup_query(text) and intent.photo_lookup_query(text, rows):
        return "photo"
    return "image" if intent.image_gen_request(text, rows, revisions=bool(rows)) else "none"


async def by_read(settings: Any, row: dict[str, Any]) -> str:
    """The decision as the chat turn (or, with a photo attached, the composer) makes it."""
    from app.modules.chat.drawn_picture import read_picture
    from app.modules.chat.picture_ask import read_picture_ask
    from app.modules.chat.turn_decision import start_turn_decision
    from app.modules.images import intent
    from app.modules.images.lookup_intent import extract_image_lookup_query

    rows, labels = stored_rows(row["history"])
    text = row["prompt"]
    if row.get("attached"):
        candidates = intent.composer_candidates(text, rows, image_attached=True, labels=labels)
        asked = None
        if candidates.request is not None or candidates.lookup_query:
            asked = await read_picture_ask(settings, text, rows, pictures=labels)
        found = intent.decided_intent(candidates, asked)
        return "image" if found.request else "photo" if found.lookup_query else "none"
    words = intent.PictureCandidates(
        lookup_query=extract_image_lookup_query(text),
        request=intent.image_gen_request(text, rows, revisions=bool(rows), labels=labels),
    )
    if not words.any:
        return "none"
    done: asyncio.Future[dict[uuid.UUID, Any]] = asyncio.get_running_loop().create_future()
    done.set_result(labels)
    asked = await read_picture(start_turn_decision(settings, text, recent=rows, pictures=done))
    if asked == "photo" and words.photo():
        return "photo"
    return "image" if asked == "image" and words.picture() else "none"


async def measure(rows: list[dict[str, Any]], runs: int, *, words: bool) -> dict[str, list[str]]:
    from app.core.config import Settings

    settings = Settings()
    found: dict[str, list[str]] = defaultdict(list)
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(row: dict[str, Any]) -> None:
        async with gate:
            found[row["id"]].append(words_alone(row) if words else await by_read(settings, row))

    async def never_capped(*_args: Any, **_kwargs: Any) -> bool:
        return False

    with patch("app.services.quota.global_spend_exceeded", never_capped):
        for _ in range(1 if words else runs):
            await asyncio.gather(*(one(row) for row in rows))
    return found


def report(rows: list[dict[str, Any]], found: dict[str, list[str]]) -> str:
    said: Counter[str] = Counter()
    right: Counter[str] = Counter()
    asked: Counter[str] = Counter()
    false_pictures: Counter[str] = Counter()
    seen: Counter[str] = Counter()
    misses: list[str] = []
    for row in rows:
        for got in found[row["id"]]:
            asked[row["label"]] += 1
            said[got] += 1
            seen[row["kind"]] += 1
            if got == row["label"]:
                right[got] += 1
            else:
                misses.append(f"  {row['id']:<18} {row['prompt']!r:<44} {row['label']} -> {got}")
            if row["label"] == "none" and got != "none":
                false_pictures[row["kind"]] += 1
    lines = []
    for kind in _KINDS:
        precision = right[kind] / said[kind] if said[kind] else 1.0
        recall = right[kind] / asked[kind] if asked[kind] else 1.0
        lines.append(
            f"{kind:<6} precision {precision:.0%} ({right[kind]}/{said[kind]})  "
            f"recall {recall:.0%} ({right[kind]}/{asked[kind]})"
        )
    requests = asked["image"] + asked["photo"]
    lines.append(f"requests answered {right['image'] + right['photo']}/{requests}")
    for kind in ("complaint", "lookalike", "attached"):
        lines.append(f"false pictures on {kind}: {false_pictures[kind]}/{seen[kind]}")
    return "\n".join([*lines, "misses:", *sorted(set(misses))])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--words", action="store_true", help="the word rules alone, as before")
    args = parser.parse_args()
    rows = load()
    print(report(rows, asyncio.run(measure(rows, args.runs, words=args.words))))


if __name__ == "__main__":
    main()
