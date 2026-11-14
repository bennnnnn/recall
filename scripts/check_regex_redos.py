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
0.25 s.

regexploit reads a pattern once per way through its optional groups and alternatives, and a few
patterns have millions. Past 2,000 of them (a count, not a clock, so a slower runner rates the
same patterns), or where regexploit fails, a pattern is timed instead: on runs of space, "?",
".", "!", digits and letters, alone, before and after strings its own grammar reads (cut at
each space), at 20,000 characters, failing over 0.25 s. That catches a slow pattern, quadratic
included, that regexploit never rates.

Importing the app must never reach the network: litellm reads its bundled price list
(``LITELLM_LOCAL_MODEL_COST_MAP``, set here and in CI).

Fix one by giving each run of space one reading: end a lazy part on a mark (``.*?\\S``) and
read the space beside it possessively (``\\s++``, ``\\s*+``; Python 3.11+).
"""

from __future__ import annotations

import ast
import importlib
import os
import pkgutil
import random
import re
import signal
import sys
import time
import warnings
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import sre_constants as sre
    import sre_parse

    from regexploit.ast.sequence import Sequence
    from regexploit.ast.sre import SreOpParser
    from regexploit.languages.python_node_visitor import PythonNodeVisitor
    from regexploit.redos import Redos, expand_branches, find_redos_in_branchless_sequence

# regexploit's own line: a quadratic one is common and slow only on far longer input.
_WORST_ALLOWED = 2
# Each input a pattern is timed on is this long, and must read within this time.
_LENGTH = 20_000
_SECONDS = 0.25
# How many ways through a pattern regexploit reads before the pattern is timed instead.
_RATING_WAYS = 2_000
# A stop for the whole rating, far past what 2,000 ways take; it too sends the pattern to timing.
_RATING_SECONDS = 60.0
# The runs a pattern is timed on, and how many strings of its grammar and cuts of each.
_RUNS = (" ", "?", ".", "!", "1", "a")
_SAMPLES = 8
_CUTS = 30
_POOL = "abcxyzXYZ019 .,;:?!-+*/=()[]{}|_'\"\t\n%$"

# (pattern, flags) -> where it lives.
Found = dict[tuple[str, int], str]


class _Slow(Exception):
    pass


class _TooMany(Exception):
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


def _find(parsed: Any) -> list[Redos]:
    """regexploit's findings, read way by way; ``_TooMany`` past ``_RATING_WAYS`` of them."""
    if parsed is None:
        return []
    sequence = parsed if isinstance(parsed, Sequence) else Sequence([parsed])
    found: list[Redos] = []
    for count, way in enumerate(expand_branches(sequence), 1):
        if count > _RATING_WAYS:
            raise _TooMany
        found += [redos for redos in find_redos_in_branchless_sequence(way) if redos not in found]
    return found


def _rate(pattern: str, flags: int) -> tuple[list[Redos], bool]:
    """regexploit's findings, and whether possessive or atomic marks were read as plain."""
    try:
        parsed, plain_copy = SreOpParser().parse_sre(pattern, flags), False
    except AttributeError:
        parsed, plain_copy = _PlainParser().parse_sre(pattern, flags), True
    return _find(parsed), plain_copy


def _example(redos: Redos, length: int) -> str:
    """regexploit's input for one finding, its repeated part long enough to fill ``length``."""
    repeated, killer = redos.repeated_character, redos.killer
    if killer and (both := repeated & killer):
        repeated, killer = both, None
    prefix, tail = redos.example_prefix, killer.example() if killer else ""
    unit = repeated.example()
    return prefix + unit * max(1, (length - len(prefix) - len(tail)) // len(unit)) + tail


def _seconds(pattern: re.Pattern[str], text: str, *, search: bool = False) -> float:
    """How long the pattern takes to read ``text``, cut off at 4 x the budget."""
    started = time.perf_counter()
    signal.setitimer(signal.ITIMER_REAL, _SECONDS * 4)
    try:
        pattern.search(text) if search else pattern.match(text)
    except _Slow:
        pass
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    return time.perf_counter() - started


def _fits(items: list[tuple[Any, Any]], char: str, flags: int) -> bool:
    """Whether ``char`` is in the character class ``items`` (sre's IN)."""
    hit, negate = False, False
    for op, value in items:
        if op is sre.NEGATE:
            negate = True
        elif op is sre.LITERAL:
            hit |= chr(value) == char or bool(flags & re.I and chr(value).lower() == char.lower())
        elif op is sre.RANGE:
            hit |= value[0] <= ord(char) <= value[1]
        elif op is sre.CATEGORY:
            name = value.name
            kind = (
                char.isdigit()
                if "DIGIT" in name
                else char.isspace()
                if "SPACE" in name
                else (char.isalnum() or char == "_")
            )
            hit |= (not kind) if "NOT" in name else kind
    return hit != negate


class _Grammar:
    """Strings the pattern's own grammar reads: each repeat its least, once, or a few times."""

    def __init__(self, flags: int, rng: random.Random, mode: str) -> None:
        self.flags, self.rng, self.mode, self.groups = flags, rng, mode, {}

    def text(self, ops: Any) -> str:
        return "".join(self.op(op, value) for op, value in ops)

    def op(self, op: Any, value: Any) -> str:
        pick = self.rng.choice if self.mode == "random" else (lambda options: options[0])
        if op is sre.LITERAL:
            return chr(value)
        if op in (sre.NOT_LITERAL, sre.ANY):
            return pick([c for c in "a1 " if op is sre.ANY or c != chr(value)])
        if op is sre.IN:
            literals = [chr(v) for o, v in value if o is sre.LITERAL]
            negated = any(o is sre.NEGATE for o, _ in value)
            fits = [c for c in _POOL if _fits(value, c, self.flags)]
            return pick((literals if literals and not negated else fits) or [""])
        if op in (sre.MAX_REPEAT, sre.MIN_REPEAT, getattr(sre, "POSSESSIVE_REPEAT", None)):
            least, most, inner = value
            most = least + 3 if most is sre.MAXREPEAT else most
            times = {"least": least, "once": max(least, min(1, most))}.get(
                self.mode, self.rng.randint(least, min(most, least + 3))
            )
            return "".join(self.text(inner) for _ in range(times))
        if op is sre.BRANCH:
            return self.text(pick(value[1]))
        if op is sre.SUBPATTERN:
            self.groups[value[0]] = found = self.text(value[3])
            return found
        if op is getattr(sre, "ATOMIC_GROUP", None):
            return self.text(value)
        if op is sre.GROUPREF:
            return self.groups.get(value, "")
        if op is sre.GROUPREF_EXISTS:
            return self.text(pick([value[1], value[2] or []]))
        return ""  # A position (^, $, \b) or a look-around reads nothing.


def _probes(pattern: str, flags: int) -> Iterator[tuple[str, str, str]]:
    """(text before the run, the run's character, text after): runs alone, after each cut of a
    string the grammar reads, and before the whole of one."""
    tree = sre_parse.parse(pattern, flags)
    rng = random.Random(pattern)
    modes = ["least", "once"] + ["random"] * (_SAMPLES - 2)
    samples = {_Grammar(flags, rng, mode).text(tree) for mode in modes}
    for run in _RUNS:
        yield "", run, "\x00"
        for sample in sorted(samples):
            cuts = [i for i, c in enumerate(sample) if c.isspace()] + [len(sample)]
            for cut in cuts[:: max(1, len(cuts) // _CUTS)]:
                yield sample[:cut], run, "\x00"
            yield "", run, sample + "\x00"


def _timed(pattern: str, flags: int, where: str) -> str | None:
    """A report line when one of the pattern's probes reads slowly, else None."""
    compiled = re.compile(pattern, flags)
    for before, run, after in _probes(pattern, flags):
        count = max(1, (_LENGTH - len(before) - len(after)) // len(run))
        text = before + run * count + after
        if (seconds := _seconds(compiled, text, search=True)) > _SECONDS:
            return (
                f"{where}: {seconds:.2f} s on {len(text):,} characters in {pattern!r} "
                f"(not rated; try {before!r} + {run!r} * {count} + {after!r})"
            )
    return None


def _rated(pattern: str, flags: int, where: str, found: list[Redos], plain: bool) -> str | None:
    """A report line for regexploit's worst finding that holds on the real pattern, else None."""
    compiled = re.compile(pattern, flags)
    for redos in (r for r in found if r.starriness > _WORST_ALLOWED):
        if not plain:
            return (
                f"{where}: backtracking of degree {redos.starriness} in {pattern!r} "
                f"(try {redos.example()!r})"
            )
        text = _example(redos, _LENGTH)
        if (seconds := _seconds(compiled, text)) > _SECONDS:
            return (
                f"{where}: {seconds:.2f} s on {len(text):,} characters in {pattern!r} "
                f"(its copy without possessive marks: degree {redos.starriness}, "
                f"try {redos.example()!r})"
            )
    return None


def _check(item: tuple[tuple[str, int], str]) -> tuple[str, str | None]:
    """("rated" | "timed", a report line when the pattern is slow)."""
    (pattern, flags), where = item
    signal.signal(signal.SIGALRM, _raise_slow)
    signal.setitimer(signal.ITIMER_REAL, _RATING_SECONDS)
    try:
        found, plain = _rate(pattern, flags)
    except re.error:
        return "rated", None  # Not a regex: a fragment of one, or prose the source scan read.
    except Exception:
        # Too many ways through it, or a limit of regexploit's own: time it instead.
        signal.setitimer(signal.ITIMER_REAL, 0)
        return "timed", _timed(pattern, flags, where)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    return "rated", _rated(pattern, flags, where, found, plain)


def _worth_rating(pattern: str) -> bool:
    """regexploit's own first cut: backtracking needs two repeats."""
    return pattern.count("*") + pattern.count("+") + pattern.count(",}") >= 2


def main(package: str = "app") -> int:
    started = time.perf_counter()
    sys.path.insert(0, os.getcwd())
    # Importing the app must not fetch litellm's price list from GitHub.
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        found = _compiled(package)
    for key, where in _inline(Path(package)).items():
        found.setdefault(key, where)
    items = sorted((key, where) for key, where in found.items() if _worth_rating(key[0]))
    with warnings.catch_warnings(), ProcessPoolExecutor() as pool:
        warnings.simplefilter("ignore")
        results = list(pool.map(_check, items, chunksize=2))
    slow = [line for _, line in results if line]
    for line in slow:
        print(line)
    timed = sum(status == "timed" for status, _ in results)
    print(
        f"{len(found)} regexes, {len(items) - timed} rated, {timed} timed, "
        f"{len(slow)} slow ({time.perf_counter() - started:.0f} s)"
    )
    return 1 if slow else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
