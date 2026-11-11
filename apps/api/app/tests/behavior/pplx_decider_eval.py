"""Perplexity's Decider as the turn's read, measured on the same labelled sets as the Qwen read.

A script, not a test: ``collect`` calls the Decider through OpenRouter (a key in the
environment, nothing else); ``report`` reads what ``collect`` wrote.

    python -m app.tests.behavior.pplx_decider_eval collect out.json
    python -m app.tests.behavior.pplx_decider_eval report out.json

Every turn of ``decider_corpus.json``, ``think_need_corpus.json`` and
``search_need_corpus.json`` is asked of both Decider models (Flash, 4B, and the 27B) with
seven questions: subject, picture and follow (choices), think, hard, live and asked (yes or
no, as a probability). ``report`` picks each yes threshold and the 27B's confidence floor on
the tuning half (turn ids hashed in two; the thresholds in ``chat.decider_read`` came from
it) and reports on the other half: per-field accuracy,
think recall and false thinking, search recall and false searches, latency, cost, failures.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.modules.chat.decider_read import QUESTIONS

HERE = Path(__file__).parent
MODELS = {"flash": "perplexity/pplx-decider-flash-v1.2", "large": "perplexity/pplx-decider-v1.2"}
_CONCURRENCY = 3
_SECONDS = 3.0


def tuning(turn_id: str) -> bool:
    """The half thresholds are picked on; the other half is reported."""
    return hashlib.sha256(turn_id.encode()).digest()[0] % 2 == 0


def _items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in json.loads((HERE / "decider_corpus.json").read_text(encoding="utf-8")):
        items.append(
            {
                "set": "decider",
                "id": row["id"],
                "prompt": row["prompt"],
                "history": row["history"],
                "labels": {k: row[k] for k in ("subject", "effort", "picture", "follow")},
            }
        )
    for row in json.loads((HERE / "think_need_corpus.json").read_text(encoding="utf-8")):
        items.append(
            {
                "set": "think",
                "id": row["id"],
                "prompt": row["prompt"],
                "history": row.get("history", []),
                "labels": {"think": row["think"]},
            }
        )
    from app.tests.behavior.search_need_eval import load

    for turn in load():
        items.append(
            {
                "set": "search",
                "id": turn.id,
                "prompt": turn.prompt,
                "history": [list(p) for p in turn.history],
                "labels": {"live": turn.live},
            }
        )
    return items


def state_of(prompt: str, history: list[list[str]]) -> str:
    """The text the Decider judges: the earlier turns quoted, then the last message, as the
    Qwen read sees them (``turn_decision.decision_messages``)."""
    from app.modules.chat import turn_decision

    rows = [SimpleNamespace(role=role, content=text) for role, text in history]
    return turn_decision.decision_messages(prompt, turn_decision.earlier_turns(rows))[-1]["content"]


async def collect() -> list[dict[str, Any]]:
    from app.core.config import Settings
    from app.gateways.decider_gateway import decide

    settings = Settings()
    items = _items()
    gate = asyncio.Semaphore(_CONCURRENCY)
    out: list[dict[str, Any]] = []

    async def one(item: dict[str, Any], name: str) -> None:
        async with gate:
            started = time.monotonic()
            try:
                reply = await decide(
                    settings,
                    model=MODELS[name],
                    state=state_of(item["prompt"], item["history"]),
                    questions=QUESTIONS,
                    seconds=_SECONDS,
                )
                answers = {k: v.model_dump() for k, v in reply.answers.items()}
                cost, error = reply.usage.cost, None
            except Exception as exc:  # A failure is a result: the rules would decide.
                status = getattr(getattr(exc, "response", None), "status_code", "")
                answers, cost, error = {}, 0.0, f"{type(exc).__name__}{status}"
            out.append(
                {
                    **item,
                    "model": name,
                    "answers": answers,
                    "cost": cost,
                    "error": error,
                    "seconds": time.monotonic() - started,
                }
            )

    await asyncio.gather(*(one(item, name) for item in items for name in MODELS))
    return out


def _ok(label: str, value: str | None) -> bool:
    return value is not None and value in label.split("|")


def _scores(rows: list[dict[str, Any]]) -> str:
    """Per field, with the product's thresholds (``decider_read.decision_fields``)."""
    from app.modules.chat.decider_read import decision_fields

    read: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for row in rows:
        fields = decision_fields(row["answers"], has_earlier=bool(row["history"]))
        if fields is not None:
            read.append((row, fields))
    dec = [(r, f) for r, f in read if r["set"] == "decider"]
    parts = [
        f"{name} {sum(_ok(r['labels'][name], f[name]) for r, f in dec) / max(1, len(dec)):.1%}"
        for name in ("subject", "picture", "follow")
    ]
    # Thinking or not, against the effort label (STEM's "high" is its one level that thinks).
    agree = [f["think"] in {e != "none" for e in r["labels"]["effort"].split("|")} for r, f in dec]
    parts.append(f"thinks {sum(agree) / max(1, len(agree)):.1%}")
    think = [(r["labels"]["think"], f["think"]) for r, f in read if r["set"] == "think"]
    live = [(r["labels"]["live"], f["live"] or f["asked"]) for r, f in read if r["set"] == "search"]
    for name, pairs in (("think", think), ("search", live)):
        yes = [said for want, said in pairs if want]
        no = [said for want, said in pairs if not want]
        parts.append(
            f"{name} recall {sum(yes) / max(1, len(yes)):.1%} false {sum(no) / max(1, len(no)):.1%}"
        )
    return "  ".join(parts)


def report(rows: list[dict[str, Any]]) -> str:
    lines = []
    for name in MODELS:
        group = [r for r in rows if r["model"] == name]
        ok = [r for r in group if r["error"] is None]
        secs = sorted(r["seconds"] for r in group)
        lines.append(
            f"{name}: failed {len(group) - len(ok)}/{len(group)}  p50 "
            f"{statistics.median(secs):.2f}s p95 {secs[int(len(secs) * 0.95)]:.2f}s  "
            f"cost ${statistics.mean(r['cost'] for r in ok):.7f}"
        )
        lines.append(f"  held-out: {_scores([r for r in ok if not tuning(r['id'])])}")
        lines.append(f"  tuning:   {_scores([r for r in ok if tuning(r['id'])])}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("collect", "report"))
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.mode == "collect":
        rows = asyncio.run(collect())
        args.path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(report(json.loads(args.path.read_text(encoding="utf-8"))))


if __name__ == "__main__":
    main()
