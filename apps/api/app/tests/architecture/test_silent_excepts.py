"""A broad ``except`` that swallows its error may only grow rarer.

An ``except Exception`` (or ``BaseException``, or a bare ``except``) whose body neither
raises nor reports the error (a ``logger`` or ``logging`` call, a ``capture_*`` call)
hides a failure: production records nothing, and the turn quietly does something else.
Today's are counted per file in ``silent_except_baseline.json``; no file may gain one.
Log the error at the level it deserves, or catch the exceptions you expect by name.
After removing one, rerun with ``UPDATE_SILENT_EXCEPTS=1`` to lower the count.
"""

from __future__ import annotations

import ast
import json
import os
from collections import Counter
from pathlib import Path

from .boundary_support import APP_ROOT

_BASELINE = Path(__file__).with_name("silent_except_baseline.json")
_BROAD = frozenset({"Exception", "BaseException"})
_LOGGERS = frozenset({"logger", "logging", "log", "_logger", "_log"})


def _is_broad(caught: ast.expr | None) -> bool:
    if caught is None:
        return True
    if isinstance(caught, ast.Name):
        return caught.id in _BROAD
    if isinstance(caught, ast.Attribute):
        return caught.attr in _BROAD
    if isinstance(caught, ast.Tuple):
        return any(_is_broad(element) for element in caught.elts)
    return False


def _reports(call: ast.Call) -> bool:
    """``logger.warning(...)``, ``logging.exception(...)``, ``sentry_sdk.capture_exception(...)``."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id.startswith("capture_")
    if not isinstance(func, ast.Attribute):
        return False
    owner = func.value
    name = owner.id if isinstance(owner, ast.Name) else getattr(owner, "attr", "")
    return name in _LOGGERS or func.attr.startswith("capture_")


def _is_silent(handler: ast.ExceptHandler) -> bool:
    for statement in handler.body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Raise) or (isinstance(node, ast.Call) and _reports(node)):
                return False
    return True


def _silent_counts(trees: dict[str, ast.AST]) -> dict[str, int]:
    """File -> broad handlers that neither raise nor report."""
    counts: Counter[str] = Counter()
    for file, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and _is_broad(node.type) and _is_silent(node):
                counts[file] += 1
    return dict(sorted(counts.items()))


def _production_counts() -> dict[str, int]:
    trees: dict[str, ast.AST] = {}
    for path in sorted(APP_ROOT.rglob("*.py")):
        relative = path.relative_to(APP_ROOT)
        if "tests" not in relative.parts and "__pycache__" not in relative.parts:
            trees[relative.as_posix()] = ast.parse(path.read_text())
    return _silent_counts(trees)


def _recorded(counts: dict[str, int]) -> dict[str, int]:
    recorded: dict[str, int] = json.loads(_BASELINE.read_text())
    if os.environ.get("UPDATE_SILENT_EXCEPTS"):
        recorded = {
            file: min(count, counts[file])
            for file, count in sorted(recorded.items())
            if counts.get(file, 0) > 0
        }
        _BASELINE.write_text(json.dumps(recorded, indent=2) + "\n")
    return recorded


def test_silent_counts_only_broad_handlers_that_neither_raise_nor_report() -> None:
    source = (
        "try:\n    a()\nexcept Exception:\n    return None\n"
        "try:\n    a()\nexcept:\n    pass\n"
        "try:\n    a()\nexcept (ValueError, BaseException):\n    x = 1\n"
        "try:\n    a()\nexcept ValueError:\n    pass\n"
        "try:\n    a()\nexcept Exception:\n    logger.warning('a failed')\n"
        "try:\n    a()\nexcept Exception:\n    sentry_sdk.capture_exception()\n"
        "try:\n    a()\nexcept Exception as exc:\n    raise RuntimeError from exc\n"
        "try:\n    a()\nexcept Exception:\n    if b():\n        raise\n"
    )
    assert _silent_counts({"x.py": ast.parse(source)}) == {"x.py": 3}


def test_no_file_gains_a_silent_broad_except() -> None:
    counts = _production_counts()
    recorded = _recorded(counts)
    gained = [
        f"{file}: {recorded.get(file, 0)} -> {count}"
        for file, count in counts.items()
        if count > recorded.get(file, 0)
    ]
    assert gained == [], (
        "a broad except swallows its error: log it or catch the exceptions you expect\n  "
        + "\n  ".join(gained)
    )


def test_the_recorded_counts_are_current() -> None:
    counts = _production_counts()
    fewer = [
        f"{file}: {count} -> {counts.get(file, 0)}"
        for file, count in _recorded(counts).items()
        if counts.get(file, 0) < count
    ]
    assert fewer == [], "fewer now: rerun with UPDATE_SILENT_EXCEPTS=1 to lock it in"
