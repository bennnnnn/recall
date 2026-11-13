"""Fail when a regex the API runs can backtrack in cubic time or worse (ReDoS).

    uv run --with regexploit==1.0.0 python ../../scripts/check_regex_redos.py   (from apps/api)

A message may hold 32,000 characters and a model's reply as many; on 2026-11-13 regexploit
found readers that took over 20 s on a cue and a run of 2,000 spaces ("average value of" and
spaces, "answer" and spaces). This imports every module under app/ (tests aside) and reads each
regex as Python compiled it: a module-level pattern, one held in a tuple, list, set or dict (and
the pairs inside them), or one a class keeps. A pattern built from pieces (an f-string, ``+``, a
join) is read whole that way. A pattern written inline in a call (``re.sub(r"...", ...)``) is
read from the source as well.

regexploit rates each one; a rating above quadratic fails, with the pattern, where it lives and
an input that shows it. regexploit (unmaintained) cannot parse possessive quantifiers or atomic
groups: such a pattern is rated with those marks read as plain ones, and each input that copy is
slow on is then timed on the real pattern at 20,000 characters. It fails when that takes over
0.25 s. A pattern regexploit cannot rate (a few huge alternations take it minutes) is listed,
not failed.

Fix one by giving each run of space one reading: end a lazy part on a mark (``.*?\\S``) and
read the space beside it possessively (``\\s++``, ``\\s*+``; Python 3.11+).
"""

from __future__ import annotations

import ast
import importlib
import os
import pkgutil
import re
import signal
import sys
import time
import warnings
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from regexploit.ast.sre import SreOpParser
from regexploit.languages.python_node_visitor import PythonNodeVisitor
from regexploit.redos import Redos, find

# regexploit's own line: a quadratic one is common and slow only on far longer input.
_WORST_ALLOWED = 2
# A possessive pattern's candidate input is this long, and must read within this time.
_LENGTH = 20_000
_SECONDS = 0.25
# regexploit expands every optional group: a few huge alternations would take minutes.
_RATING_SECONDS = 4.0

# (pattern, flags) -> where it lives.
Found = dict[tuple[str, int], str]


class _Slow(Exception):
    pass


def _raise_slow(*_: object) -> None:
    raise _Slow


class _PlainParser(SreOpParser):  # type: ignore[misc]
    """Reads a possessive repeat as a greedy one and an atomic group as a plain group (the
    names are regexploit's: one method per sre opcode)."""

    def from_POSSESSIVE_REPEAT(self, data: Any) -> Any:
        return self.from_MAX_REPEAT(data)

    def from_ATOMIC_GROUP(self, data: Any) -> Any:
        return self.sequence_or_singleton(data)


def _patterns_in(
    value: object, where: str, depth: int = 0
) -> Iterator[tuple[re.Pattern[str], str]]:
    """The patterns ``value`` is or holds, with where each lives."""
    if isinstance(value, re.Pattern):
        if isinstance(value.pattern, str):
            yield value, where
    elif depth < 2 and isinstance(value, tuple | list | set | frozenset):
        for index, item in enumerate(value):
            yield from _patterns_in(item, f"{where}[{index}]", depth + 1)
    elif depth < 2 and isinstance(value, dict):
        for key, item in value.items():
            yield from _patterns_in(item, f"{where}[{key!r}]", depth + 1)


def _compiled(package: str) -> Found:
    """Every pattern the package's modules keep, as compiled (pieces joined, flags set)."""
    root = importlib.import_module(package)
    found: Found = {}
    for info in pkgutil.walk_packages(root.__path__, f"{package}."):
        if "tests" in info.name.split("."):
            continue
        module = importlib.import_module(info.name)
        for name, value in vars(module).items():
            values = [(value, f"{info.name}.{name}")]
            if isinstance(value, type) and value.__module__ == info.name:
                values += [(v, f"{info.name}.{name}.{n}") for n, v in vars(value).items()]
            for item, where in values:
                for pattern, label in _patterns_in(item, where):
                    found.setdefault((pattern.pattern, pattern.flags & ~re.UNICODE), label)
    return found


def _inline(root: Path) -> Found:
    """Patterns written in the source: inline calls the module never keeps compiled."""
    found: Found = {}
    for path in sorted(root.rglob("*.py")):
        if "tests" in path.parts:
            continue
        visitor = PythonNodeVisitor()
        visitor.visit(ast.parse(path.read_bytes()))
        for regex in visitor.patterns:
            found.setdefault((regex.pattern, regex.flags & ~re.UNICODE), f"{path}:{regex.lineno}")
    return found


def _rate(pattern: str, flags: int) -> tuple[list[Redos], bool]:
    """regexploit's findings, and whether possessive or atomic marks were read as plain."""
    try:
        return find(SreOpParser().parse_sre(pattern, flags)), False
    except AttributeError:
        return find(_PlainParser().parse_sre(pattern, flags)), True


def _example(redos: Redos, length: int) -> str:
    """regexploit's input for one finding, its repeated part long enough to fill ``length``."""
    repeated, killer = redos.repeated_character, redos.killer
    if killer and (both := repeated & killer):
        repeated, killer = both, None
    prefix, tail = redos.example_prefix, killer.example() if killer else ""
    unit = repeated.example()
    return prefix + unit * max(1, (length - len(prefix) - len(tail)) // len(unit)) + tail


def _seconds(pattern: re.Pattern[str], text: str) -> float:
    """How long the pattern takes to read ``text`` from its start, cut off at 4 x the budget."""
    started = time.perf_counter()
    signal.setitimer(signal.ITIMER_REAL, _SECONDS * 4)
    try:
        pattern.match(text)
    except _Slow:
        pass
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    return time.perf_counter() - started


def _check(item: tuple[tuple[str, int], str]) -> tuple[str, str | None]:
    """("ok" | "slow" | "unrated", a report line when it fails)."""
    (pattern, flags), where = item
    signal.signal(signal.SIGALRM, _raise_slow)
    signal.setitimer(signal.ITIMER_REAL, _RATING_SECONDS)
    try:
        found, plain_copy = _rate(pattern, flags)
    except re.error:
        return "ok", None  # Not a regex: a fragment of one, or prose the source scan picked up.
    except _Slow:
        return "unrated", f"{where}: not rated in {_RATING_SECONDS:.0f} s"
    except Exception as error:
        # regexploit's own limits: listed, never a failure of the code it reads.
        return "unrated", f"{where}: regexploit could not rate it ({type(error).__name__})"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    compiled = re.compile(pattern, flags)
    for redos in (r for r in found if r.starriness > _WORST_ALLOWED):
        if not plain_copy:
            return "slow", (
                f"{where}: backtracking of degree {redos.starriness} in {pattern!r} "
                f"(try {redos.example()!r})"
            )
        text = _example(redos, _LENGTH)
        if (seconds := _seconds(compiled, text)) > _SECONDS:
            return "slow", (
                f"{where}: {seconds:.2f} s on {len(text):,} characters in {pattern!r} "
                f"(its copy without possessive marks: degree {redos.starriness}, "
                f"try {redos.example()!r})"
            )
    return "ok", None


def _worth_rating(pattern: str) -> bool:
    """regexploit's own first cut: backtracking needs two repeats."""
    return pattern.count("*") + pattern.count("+") + pattern.count(",}") >= 2


def main(package: str = "app") -> int:
    started = time.perf_counter()
    sys.path.insert(0, os.getcwd())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        found = _compiled(package)
    for key, where in _inline(Path(package)).items():
        found.setdefault(key, where)
    items = sorted((key, where) for key, where in found.items() if _worth_rating(key[0]))
    with warnings.catch_warnings(), ProcessPoolExecutor() as pool:
        warnings.simplefilter("ignore")
        results = list(pool.map(_check, items, chunksize=4))
    slow = [line for status, line in results if status == "slow" and line]
    unrated = [line for status, line in results if status == "unrated" and line]
    for line in unrated:
        print(f"note: {line}")
    for line in slow:
        print(line)
    print(
        f"{len(found)} regexes, {len(items)} rated, {len(unrated)} not rated, "
        f"{len(slow)} that backtrack in cubic time or worse "
        f"({time.perf_counter() - started:.0f} s)"
    )
    return 1 if slow else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
