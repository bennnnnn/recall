"""A broad ``except`` that swallows its error may only grow rarer.

An ``except Exception`` (or ``BaseException``, or a bare ``except``) whose body neither
raises nor reports the error hides a failure: production records nothing, and the turn
quietly does something else. Reporting means a log call at info level or above
(production logs at INFO, so a ``logger.debug`` alone is silent there) or a Sentry
``capture_exception``/``capture_message``; a raise or log inside a nested function is not
the handler's. A ``with suppress(Exception)`` is the same swallow and counts too.

Today's are counted per file in ``silent_except_baseline.json``; no file may gain one.
Log the error at the level it deserves, or catch the exceptions you expect by name.
After removing one, rerun with ``UPDATE_SILENT_EXCEPTS=1`` to lower the count.
"""

from __future__ import annotations

import ast
import json
import os
from collections import Counter
from collections.abc import Iterator
from functools import cache
from pathlib import Path

from .boundary_support import APP_ROOT

_BASELINE = Path(__file__).with_name("silent_except_baseline.json")
_BROAD = frozenset({"Exception", "BaseException"})
_REPORTING_LEVELS = frozenset(
    {"info", "warning", "warn", "error", "exception", "critical", "fatal", "log"}
)
_LOGGERS = frozenset({"log", "logger", "logging"})
_SENTRY = frozenset({"capture_exception", "capture_message"})


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
    """``logger.warning(...)``, ``logging.exception(...)``, ``sentry_sdk.capture_exception()``."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id in _SENTRY
    if not isinstance(func, ast.Attribute):
        return False
    if func.attr in _SENTRY:
        return True
    owner = func.value
    name = (owner.id if isinstance(owner, ast.Name) else getattr(owner, "attr", "")).lower()
    is_logger = name.lstrip("_") in _LOGGERS or name.endswith("logger")
    if not is_logger or func.attr not in _REPORTING_LEVELS:
        return False
    return func.attr != "log" or _reported_level(call)


def _reported_level(call: ast.Call) -> bool:
    """``logger.log(level, …)`` reports at INFO or above; ``logging.DEBUG`` (or any level
    below 20) never reaches production logs. A level held in a variable gets the benefit."""
    level = (
        call.args[0]
        if call.args
        else next((kw.value for kw in call.keywords if kw.arg == "level"), None)
    )
    if isinstance(level, ast.Attribute):
        return level.attr in {"INFO", "WARNING", "WARN", "ERROR", "CRITICAL", "FATAL"}
    if isinstance(level, ast.Constant) and isinstance(level.value, int):
        return level.value >= 20
    return level is not None


def _own_nodes(statements: list[ast.stmt]) -> Iterator[ast.AST]:
    """Every node of ``statements`` outside nested functions and classes."""
    stack: list[ast.AST] = list(statements)
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Lambda):
            stack.extend(ast.iter_child_nodes(node))


def _is_silent(handler: ast.ExceptHandler) -> bool:
    return not any(
        isinstance(node, ast.Raise) or (isinstance(node, ast.Call) and _reports(node))
        for node in _own_nodes(handler.body)
    )


def _suppresses_broadly(node: ast.AST) -> bool:
    """``suppress(Exception)``, ``contextlib.suppress(ValueError, BaseException)``."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    return name == "suppress" and any(_is_broad(argument) for argument in node.args)


def _silent_counts(trees: dict[str, ast.AST]) -> dict[str, int]:
    """File -> broad handlers that neither raise nor report, and broad ``suppress`` calls."""
    counts: Counter[str] = Counter()
    for file, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and _is_broad(node.type) and _is_silent(node):
                counts[file] += 1
            elif _suppresses_broadly(node):
                counts[file] += 1
    return dict(sorted(counts.items()))


@cache
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


def test_silent_counts_only_broad_swallows() -> None:
    silent = (
        "try:\n    a()\nexcept Exception:\n    return None\n",
        "try:\n    a()\nexcept:\n    pass\n",
        "try:\n    a()\nexcept (ValueError, BaseException):\n    x = 1\n",
        "try:\n    a()\nexcept Exception as exc:\n    logger.debug('a failed: %s', exc)\n",
        "try:\n    a()\nexcept Exception as exc:\n    log.append(exc)\n",
        "try:\n    a()\nexcept Exception:\n    catalog.info('a')\n",
        "try:\n    a()\nexcept Exception:\n    def later():\n        raise ValueError\n",
        "try:\n    a()\nexcept* Exception:\n    pass\n",
        "with contextlib.suppress(Exception):\n    a()\n",
        "with suppress(ValueError, BaseException):\n    a()\n",
        # 2026-11-01: a DEBUG line through ``log`` never reaches production logs either.
        "try:\n    a()\nexcept Exception:\n    logger.log(logging.DEBUG, 'a failed')\n",
        "try:\n    a()\nexcept Exception:\n    logger.log(10, 'a failed')\n",
    )
    reported = (
        "try:\n    a()\nexcept ValueError:\n    pass\n",
        "with suppress(ValueError):\n    a()\n",
        "try:\n    a()\nexcept Exception:\n    logger.warning('a failed')\n",
        "try:\n    a()\nexcept Exception:\n    self._logger.info('a failed')\n",
        "try:\n    a()\nexcept Exception:\n    logging.exception('a failed')\n",
        "try:\n    a()\nexcept Exception:\n    sentry_sdk.capture_exception()\n",
        "try:\n    a()\nexcept Exception as exc:\n    raise RuntimeError from exc\n",
        "try:\n    a()\nexcept Exception:\n    if b():\n        raise\n",
        "try:\n    a()\nexcept Exception:\n    logger.log(logging.WARNING, 'a failed')\n",
        "try:\n    a()\nexcept Exception:\n    logger.log(level, 'a failed')\n",
    )
    assert _silent_counts({"x.py": ast.parse("".join(silent))}) == {"x.py": len(silent)}
    assert _silent_counts({"x.py": ast.parse("".join(reported))}) == {}


def test_no_file_gains_a_silent_broad_except() -> None:
    counts = _production_counts()
    recorded = _recorded(counts)
    gained = [
        f"{file}: {recorded.get(file, 0)} -> {count}"
        for file, count in counts.items()
        if count > recorded.get(file, 0)
    ]
    assert gained == [], (
        "a broad except or suppress swallows its error: log it at info or above, or catch"
        " the exceptions you expect by name\n  " + "\n  ".join(gained)
    )


def test_the_recorded_counts_are_current() -> None:
    counts = _production_counts()
    fewer = [
        f"{file}: {count} -> {counts.get(file, 0)}"
        for file, count in _recorded(counts).items()
        if counts.get(file, 0) < count
    ]
    assert fewer == [], "fewer now: rerun with UPDATE_SILENT_EXCEPTS=1 to lock it in"
