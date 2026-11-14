"""Every catalog law solved for each of its inputs, worked out once by SymPy and kept.

``inverse.rearranged`` solves a law for one of its inputs with ``sympy.solve``. A turn
waited on it the first time a worker met each law: 0.3 s for most, 1.4 s for an angle on
an incline, 25 s for the 891 the physics catalog can ask (review, 2026-11-12). The pool's
workers recycle every 500 jobs, so a worker forgot them again. The answers are fixed by
the catalog's own arithmetic, so they are worked out ahead and kept in
``rearrangements.json``; SymPy still works out anything the file lacks.

A row of ``rearranged`` is ``[expression, result, unknown, solution or null]``; a row of
``keeps_its_size`` is ``[solution, result, true or false]``. A test works every row out
again and holds the rows to the catalog, so the file is never stale:
``uv run python -m app.tests.modules.physics.rearrangement_table`` writes it.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

TABLE_PATH = Path(__file__).with_name("rearrangements.json")


@cache
def _table() -> dict[str, list[list[object]]]:
    table: dict[str, list[list[object]]] = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    return table


@cache
def kept_rearrangements() -> dict[tuple[str, str, str], str | None]:
    """(expression, result, unknown) -> the solution SymPy gives, or None when it gives none."""
    return {
        (str(expression), str(result), str(unknown)): None if solution is None else str(solution)
        for expression, result, unknown, solution in _table()["rearranged"]
    }


@cache
def kept_sizes() -> dict[tuple[str, str], bool]:
    """(solution, result) -> whether the solution keeps its size when the result's sign flips."""
    return {
        (str(solution), str(result)): bool(keeps)
        for solution, result, keeps in _table()["keeps_its_size"]
    }
