"""Fail a pull request that makes a turn's server work clearly slower than main's.

    python scripts/bench_api.py inputs > inputs.json            # from the pull request's tree
    python scripts/bench_api.py time <apps/api dir> inputs.json  # each tree, in a fresh process
    python scripts/bench_api.py compare base.json head.json     # exit 1 on a regression

Every turn reads its message (the maths, physics and chemistry readers, its plan) and lays its
reply out (the presentation pass); those run on every message, so a slower pattern or a loop
gone quadratic costs every user. The benchmark runs that code over a fixed sample of the test
corpora: the same inputs for main and the pull request, on the same machine, three fresh
processes each, keeping each side's fastest. A benchmark is a regression when the pull request
takes more than 30% longer and at least 50 ms more over its whole sample, a margin CI noise
does not reach. No account or stored history: the base is the pull request's merge base.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

_SAMPLE = 80
_RUNS = 3
_MOST_RATIO = 1.30
_LEAST_SECONDS = 0.05


def _corpus_prompts(api: Path, subject: str) -> list[str]:
    prompts: list[str] = []
    for path in sorted(
        (api / "app/tests/behavior/stem_corpus" / subject).glob("*.json")
    ):
        prompts += [
            item["prompt"]
            for item in json.loads(path.read_text())
            if item.get("prompt")
        ]
    return prompts[:: max(1, len(prompts) // _SAMPLE)][:_SAMPLE]


def _inputs() -> dict[str, list[str]]:
    api = Path(__file__).resolve().parents[1] / "apps/api"
    replies: list[str] = []
    for path in sorted((api / "app/tests/behavior/sweep_corpus").glob("*.json")):
        replies += [
            item["reply"] for item in json.loads(path.read_text()) if item.get("reply")
        ]
    maths, physics, chemistry = (
        _corpus_prompts(api, s) for s in ("math", "physics", "chemistry")
    )
    return {
        "maths": maths,
        "physics": physics,
        "chemistry": chemistry,
        "plan": maths[::2] + physics[::2] + chemistry[::2],
        "replies": sorted(replies, key=len)[-_SAMPLE:],
    }


def _benchmarks() -> dict[str, tuple[str, Callable[[str], Any]]]:
    """Each benchmark's input set and the code it times, as the tree being timed has it."""
    from app.core.config import Settings
    from app.modules.chat.presentation import present_assistant_markdown
    from app.modules.chat.turn_prep.reading import plan_of
    from app.modules.chemistry.extract import extract_chemistry_intent
    from app.modules.math.tools.extract import extract_math_intent
    from app.modules.physics.extract import extract_physics_intent

    settings = Settings()
    return {
        "maths reader": ("maths", extract_math_intent),
        "physics reader": ("physics", extract_physics_intent),
        "chemistry reader": ("chemistry", extract_chemistry_intent),
        "turn plan": ("plan", lambda text: plan_of(text, settings)),
        "reply presentation": ("replies", present_assistant_markdown),
    }


def _time_once(inputs: dict[str, list[str]]) -> dict[str, float]:
    found = {}
    for name, (sample, run) in _benchmarks().items():
        started = time.perf_counter()
        for text in inputs[sample]:
            run(text)
        found[name] = time.perf_counter() - started
    return found


def _time(api_dir: str, inputs_path: str) -> dict[str, float]:
    """Each benchmark's fastest of ``_RUNS`` fresh processes: per-text caches start empty."""
    best: dict[str, float] = {}
    for _ in range(_RUNS):
        out = subprocess.run(
            [sys.executable, __file__, "_once", inputs_path],
            cwd=api_dir,
            env={**_env(), "PYTHONPATH": api_dir},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for name, seconds in json.loads(out.strip().splitlines()[-1]).items():
            best[name] = min(seconds, best.get(name, seconds))
    return best


def _env() -> dict[str, str]:
    import os

    return {
        **os.environ,
        "DATABASE_URL": os.environ.get(
            "DATABASE_URL", "postgresql+asyncpg://bench@127.0.0.1:1/none"
        ),
    }


def _compare(base: dict[str, float], head: dict[str, float]) -> tuple[list[str], bool]:
    lines = ["| Benchmark | main | this PR | change |", "|---|---|---|---|"]
    slower = False
    for name, after in head.items():
        before = base.get(name)
        if before is None:
            lines.append(f"| {name} | – | {after * 1000:.0f} ms | new |")
            continue
        ratio = after / before if before else 1.0
        regressed = ratio > _MOST_RATIO and after - before >= _LEAST_SECONDS
        slower |= regressed
        mark = " ⚠️ slower" if regressed else ""
        lines.append(
            f"| {name} | {before * 1000:.0f} ms | {after * 1000:.0f} ms | {ratio - 1:+.0%}{mark} |"
        )
    return lines, slower


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""
    if command == "inputs":
        print(json.dumps(_inputs(), ensure_ascii=False))
        return 0
    if command == "_once":
        print(json.dumps(_time_once(json.loads(Path(argv[1]).read_text()))))
        return 0
    if command == "time":
        print(
            json.dumps(
                _time(str(Path(argv[1]).resolve()), str(Path(argv[2]).resolve()))
            )
        )
        return 0
    if command == "compare":
        base, head = (json.loads(Path(path).read_text()) for path in argv[1:3])
        lines, slower = _compare(base, head)
        print("\n".join(lines))
        if slower:
            print(
                f"\nA benchmark took over {_MOST_RATIO - 1:.0%} longer than main and at least "
                f"{_LEAST_SECONDS * 1000:.0f} ms more: profile it before merging."
            )
        return 1 if slower else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
