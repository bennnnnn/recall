#!/usr/bin/env python3
"""Ask a non-Anthropic model on OpenRouter to write a change, and apply it to this checkout.

    openrouter_patch.py --model google/gemini-4-carbon --task task.md \
        apps/api/app/modules/math/figure apps/api/app/tests/modules/math --out run.json

The model gets the project's rules (as for a review), the task and the files named, and answers
with exact edits: a passage to find and its replacement, or a new file. Each edit is applied
only when its passage occurs exactly once, inside this checkout and outside .git, .github and
every .env; one edit that fails stops the run with nothing written. Nothing is committed: the
change is checked, tested and reviewed like any other before it goes anywhere. Run it in its
own worktree. The key is read from OPENROUTER_API_KEY and never written anywhere.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from openrouter_review import ROOT, ask, paths_material

PROMPT = """You write code for Recall, a mobile AI chat app (Expo React Native + FastAPI).
The project's rules follow, then the task, then the code you may change. Follow the rules:
fix the class of a defect, never one phrase; reuse what exists, never write the same logic
twice; keep files under their size limits; add or change tests that prove the change.
You cannot run anything, so read the code closely and keep the change small and exact.

Answer with JSON only, no prose around it:
{"summary": "what you changed and why, in a few sentences",
 "edits": [{"file": "path", "find": "an exact passage of the current file, long enough to
   occur once", "replace": "its new text"}],
 "new_files": [{"file": "path", "content": "the whole file"}],
 "tests": "which tests to run to prove it"}
"""

_BARRED = (".git", ".github")


def _target(path: str) -> Path:
    full = (ROOT / path).resolve()
    if ROOT.resolve() not in full.parents:
        raise SystemExit(f"refused: {path} is outside this checkout")
    rel = full.relative_to(ROOT.resolve())
    if rel.parts[0] in _BARRED or any(part.startswith(".env") for part in rel.parts):
        raise SystemExit(f"refused: {path} may not be written")
    return full


def apply(answer: dict) -> list[str]:
    """Every edit checked first, then all written: a failed edit leaves the checkout as it was."""
    pending: dict[Path, str] = {}
    for edit in answer.get("edits") or []:
        target = _target(str(edit.get("file", "")))
        text = pending.get(target) or target.read_text(encoding="utf-8")
        find, replace = str(edit.get("find", "")), str(edit.get("replace", ""))
        count = text.count(find) if find else 0
        if count != 1:
            raise SystemExit(
                f"refused: the passage occurs {count} times in {edit.get('file')}"
            )
        pending[target] = text.replace(find, replace, 1)
    for new in answer.get("new_files") or []:
        target = _target(str(new.get("file", "")))
        if target.exists():
            raise SystemExit(f"refused: {new.get('file')} already exists")
        pending[target] = str(new.get("content", ""))
    for target, text in pending.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return [str(path.relative_to(ROOT.resolve())) for path in pending]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--task", required=True, help="a file holding the task")
    parser.add_argument("--out", required=True, help="where the model's answer is kept")
    parser.add_argument(
        "--dry-run", action="store_true", help="keep the answer, write no file"
    )
    parser.add_argument(
        "targets", nargs="+", help="files and folders the model may read"
    )
    args = parser.parse_args()
    task = Path(args.task).read_text(encoding="utf-8")
    material = f"THE TASK\n{task}\n\n{paths_material(args.targets)}"
    answer = ask(args.model, material, prompt=PROMPT)
    Path(args.out).write_text(json.dumps(answer, indent=1), encoding="utf-8")
    if answer.get("unparsed"):
        raise SystemExit(f"no usable answer; see {args.out}")
    written = [] if args.dry_run else apply(answer)
    usage = answer.get("usage") or {}
    print(
        f"{len(answer.get('edits') or [])} edits, {len(answer.get('new_files') or [])} new files"
        f" from {args.model}; written: {', '.join(written) or 'none'};"
        f" cost ${usage.get('cost', '?')}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
