#!/usr/bin/env python3
"""Strict-typing ratchet for the packages that decide replies (docs/STRUCTURE_TICKETS.md ST-02).

`uv run mypy` checks these packages loosely. This runs `mypy --strict` over each one not yet in
the strict overrides of apps/api/pyproject.toml and holds its error count file by file in
scripts/mypy_strict_baseline.json: a new error fails with its file:line, and a file with fewer
errors than recorded fails until the baseline is lowered, so the count only falls. A package
that reaches none fails until it joins the strict overrides, where `uv run mypy` holds it.

Usage (from apps/api, in its virtualenv):
  uv run python ../../scripts/check_mypy_strict.py            check
  uv run python ../../scripts/check_mypy_strict.py --update   after a fix: lower the recorded
                                                              counts (never raises or adds one)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "apps" / "api"
BASELINE = ROOT / "scripts" / "mypy_strict_baseline.json"
# The packages whose code decides what a reply says.
PACKAGES = (
    "app.modules.chat",
    "app.modules.chemistry",
    "app.modules.math",
    "app.modules.money",
    "app.modules.physics",
)
_ERROR = re.compile(r"^(app/[^:]+\.py):(\d+): error: (.*)$")


def strict_packages() -> set[str]:
    """Packages pyproject.toml's strict override already holds (`uv run mypy` checks them)."""
    config = tomllib.loads((API / "pyproject.toml").read_text(encoding="utf-8"))
    held: set[str] = set()
    for override in config["tool"]["mypy"].get("overrides", []):
        if override.get("disallow_untyped_defs"):
            modules = override["module"]
            held.update([modules] if isinstance(modules, str) else modules)
    return held


def ratcheted() -> list[str]:
    held = strict_packages()
    return [package for package in PACKAGES if package not in held]


def strict_errors(packages: list[str]) -> dict[str, list[str]]:
    """file -> its strict errors as "file:line: message", for the packages given."""
    if not packages:
        return {}
    command = [
        sys.executable,
        "-m",
        "mypy",
        "--strict",
        # Imported packages are read for their types; only these packages' errors count.
        "--follow-imports=silent",
        # Strict options change every cached result: keep the loose run's cache warm.
        "--cache-dir=.mypy_cache_strict",
        "--no-error-summary",
        *(arg for package in packages for arg in ("-p", package)),
    ]
    run = subprocess.run(command, cwd=API, capture_output=True, text=True, check=False)
    if run.returncode not in (0, 1):
        raise SystemExit(f"mypy did not finish (exit {run.returncode}):\n{run.stderr or run.stdout}")
    found: dict[str, list[str]] = {}
    for line in run.stdout.splitlines():
        match = _ERROR.match(line)
        if match:
            found.setdefault(match[1], []).append(line)
    return found


def load_baseline() -> dict[str, int]:
    files: dict[str, int] = json.loads(BASELINE.read_text(encoding="utf-8"))["files"]
    return files


def package_of(path: str) -> str:
    return ".".join(Path(path).parts[:3])


def check() -> int:
    packages = ratcheted()
    found = strict_errors(packages)
    counts = Counter({path: len(lines) for path, lines in found.items()})
    recorded = load_baseline()
    problems: list[str] = []
    for path in sorted(set(counts) | set(recorded)):
        now, was = counts[path], recorded.get(path, 0)
        if package_of(path) not in packages:
            continue
        if now > was:
            problems.append(
                f"{path}: {now} strict type errors, {was} recorded. Type the new code; "
                "the file's errors are:\n    " + "\n    ".join(found[path])
            )
        elif now < was:
            problems.append(
                f"{path}: {now} strict type errors, {was} recorded. Lock the fix in: "
                "run this script with --update."
            )
    for package in packages:
        if not any(package_of(path) == package for path in counts):
            problems.append(
                f"{package} has no strict type errors: add it (and {package}.*) to the strict "
                "overrides in apps/api/pyproject.toml, then run this script with --update."
            )
    total = sum(counts.values())
    print(f"Strict typing: {total} errors in {len(counts)} files of {', '.join(packages)}.")
    for problem in problems:
        print(f"ERROR {problem}")
    return 1 if problems else 0


def update() -> int:
    packages = ratcheted()
    counts = {path: len(lines) for path, lines in strict_errors(packages).items()}
    recorded = load_baseline()
    kept = {
        path: min(counts[path], was)
        for path, was in recorded.items()
        if counts.get(path) and package_of(path) in packages
    }
    print(f"Recorded files with strict errors: {len(recorded)} -> {len(kept)}.")
    document = json.loads(BASELINE.read_text(encoding="utf-8"))
    document["files"] = dict(sorted(kept.items()))
    BASELINE.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str]) -> int:
    if argv == ["--update"]:
        return update()
    if argv:
        print(__doc__)
        return 2
    return check()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
