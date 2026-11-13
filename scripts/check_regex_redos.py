"""Fail when a regex in the API can backtrack in cubic time or worse (ReDoS).

    uv run --with regexploit==1.0.0 python ../../scripts/check_regex_redos.py app

A message may hold 32,000 characters and a model's reply as many; on 2026-11-13 regexploit
found 15 of the API's 3,260 regexes that took over 20 s on a cue and a run of 2,000 spaces
("average value of" and spaces, "answer" and spaces). This runs regexploit over every regex
the code compiles and fails on any it rates cubic or worse (its "starriness" above 2), with
the pattern, its line and an input that shows it.

Fix one by giving each run of space one reading: end a lazy part on a mark (``.*?\\S``) and
read the space beside it possessively (``\\s++``, ``\\s*+``; Python 3.11+). regexploit
(unmaintained) cannot parse possessive quantifiers or atomic groups, so a regex that uses
them is skipped: ``app/tests/architecture/test_regex_worst_cases.py`` times those on their
worst case instead.
"""

from __future__ import annotations

import ast
import re
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from regexploit.ast.sre import SreOpParser
from regexploit.languages.python_node_visitor import PythonNodeVisitor
from regexploit.redos import find

# regexploit's own line: a quadratic one is common and slow only on far longer input.
_WORST_ALLOWED = 2


def _scan(path: Path) -> list[str]:
    """Each regex in one file that backtracks worse than allowed, as a report line."""
    code = path.read_bytes()
    visitor = PythonNodeVisitor()
    visitor.visit(ast.parse(code))
    found = []
    for regex in visitor.patterns:
        try:
            parsed = SreOpParser().parse_sre(regex.pattern, regex.flags)
        except (re.error, AttributeError, NotImplementedError):
            # Not a regex, or one regexploit cannot read (possessive, atomic): skipped.
            continue
        for redos in find(parsed):
            if redos.starriness > _WORST_ALLOWED:
                found.append(
                    f"{path}:{regex.lineno}: backtracking of degree {redos.starriness} in "
                    f"{regex.pattern!r} (try {redos.example()!r})"
                )
                break
    return found


def main(roots: list[str]) -> int:
    files = sorted(
        path
        for root in roots
        for path in (Path(root).rglob("*.py") if Path(root).is_dir() else [Path(root)])
        if "tests" not in path.parts
    )
    with warnings.catch_warnings(), ProcessPoolExecutor() as pool:
        warnings.simplefilter("ignore")
        found = [line for lines in pool.map(_scan, files, chunksize=8) for line in lines]
    for line in found:
        print(line)
    print(f"{len(files)} files scanned, {len(found)} regexes that backtrack in cubic time or worse")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["app"]))
