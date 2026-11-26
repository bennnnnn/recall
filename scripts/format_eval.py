#!/usr/bin/env -S uv run python
"""Send the format corpus to a running API and judge each reply's layout.

The questions and the shape each kind wants are apps/api/app/tests/behavior/format_corpus.json
and format_shape.py. Like scripts/battery.py, this goes through the real HTTP stream on the
battery accounts (one Free, one Pro), so with a provider key the replies are the real
models'. Each reply lands in tmp/format/<plan>-<id>.md, and the run's record, with each
reply's layout and what it lacks, in tmp/format/<label>.json.

Usage (the API must be running: ./scripts/dev.sh api):
    python3 scripts/format_eval.py                  # every question, Free and Pro
    python3 scripts/format_eval.py --label after    # name the run's record
    python3 scripts/format_eval.py --plan free --kind overview
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from battery import Battery  # noqa: E402

from app.tests.behavior.format_shape import misses, shape_of  # noqa: E402

CORPUS = ROOT / "apps" / "api" / "app" / "tests" / "behavior" / "format_corpus.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--label", default="run")
    parser.add_argument("--plan", choices=("free", "pro", "both"), default="both")
    parser.add_argument("--kind", help="one kind of question")
    parser.add_argument("--out", default=str(ROOT / "tmp" / "format"))
    parser.add_argument("--rescore", help="judge a saved run's replies again, sending nothing")
    args = parser.parse_args()
    if args.rescore:
        rows = json.loads(Path(args.rescore).read_text(encoding="utf-8"))
        for row in rows:
            shape = shape_of(row["reply"])
            row["shape"] = asdict(shape)
            row["misses"] = misses(row["kind"], shape) if row["reply"] else row["misses"]
        report(rows)
        return
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    entries = json.loads(CORPUS.read_text(encoding="utf-8"))
    if args.kind:
        entries = [entry for entry in entries if entry["kind"] == args.kind]
    plans = [False, True] if args.plan == "both" else [args.plan == "pro"]
    battery = Battery(args.api)
    battery.check_api()
    rows = []
    for pro in plans:
        plan = "pro" if pro else "free"
        battery.login(pro)
        for entry in entries:
            battery._reset_quota(pro)
            battery._set_location(pro, None)
            created = battery.client.post("/chats", headers=battery._headers(pro), json={})
            created.raise_for_status()
            turn = battery._send(pro, created.json()["id"], entry["prompt"], None)
            shape = shape_of(turn.reply)
            lacks = [turn.error] if turn.error else misses(entry["kind"], shape)
            rows.append(
                {
                    **entry,
                    "plan": plan,
                    "model": turn.model,
                    "reply": turn.reply,
                    "shape": asdict(shape),
                    "misses": lacks,
                }
            )
            body = f"# {entry['prompt']}\n_{plan}, {turn.model}_\n\n{turn.reply or turn.error}\n"
            (out / f"{plan}-{entry['id']}.md").write_text(body, encoding="utf-8")
            print(f"{plan:4} {entry['id']:24} {turn.model or '':16} {', '.join(lacks) or 'ok'}")
    (out / f"{args.label}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    report(rows)


def report(rows: list[dict]) -> None:
    by: dict[tuple[str, str], list[bool]] = defaultdict(list)
    for row in rows:
        by[(row["plan"], row["kind"])].append(not row["misses"])
    print()
    for (plan, kind), passed in sorted(by.items()):
        print(f"{plan:4} {kind:9} {sum(passed)}/{len(passed)}")
    total = sum(not row["misses"] for row in rows)
    print(f"all       {total}/{len(rows)}")


if __name__ == "__main__":
    main()
