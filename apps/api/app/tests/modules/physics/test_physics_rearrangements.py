"""The kept rearrangements are SymPy's own, for every law the catalog can solve backwards.

A turn read a law solved for one of its inputs from ``law_binding/rearrangements.json``
instead of waiting on ``sympy.solve`` (review, 2026-11-12). These tests work each row out
again, so the file can never answer what SymPy would not; after a law's arithmetic
changes, ``uv run python -m app.tests.modules.physics.rearrangement_table`` writes it.
"""

from __future__ import annotations

import pytest

from app.services.law_binding import inverse
from app.services.law_binding.rearrangements import kept_rearrangements, kept_sizes
from app.tests.modules.physics.rearrangement_table import asked, worked_out

_ASKED = asked()
_REGENERATE = "uv run python -m app.tests.modules.physics.rearrangement_table"


def test_the_table_holds_every_rearrangement_the_catalog_asks() -> None:
    keys = {key for law_keys, _sized in _ASKED.values() for key in law_keys}
    missing = sorted(keys - kept_rearrangements().keys())
    stale = sorted(kept_rearrangements().keys() - keys)
    assert not missing and not stale, f"run {_REGENERATE}: {missing[:3]} {stale[:3]}"


@pytest.mark.parametrize("law", sorted(_ASKED))
def test_each_kept_rearrangement_is_sympys(law: str) -> None:
    keys, sized = _ASKED[law]
    solutions, sizes = worked_out(keys, sized)
    kept = kept_rearrangements()
    assert {key: kept.get(key, "missing") for key in keys} == solutions, f"run {_REGENERATE}"
    kept_size = kept_sizes()
    assert {key: kept_size.get(key) for key in sizes} == sizes, f"run {_REGENERATE}"


def test_a_kept_law_is_never_solved_by_sympy(monkeypatch: pytest.MonkeyPatch) -> None:
    def unused(*_args: str) -> None:
        raise AssertionError("solved by SymPy, though the table keeps it")

    monkeypatch.setattr(inverse, "sympy_rearranged", unused)
    monkeypatch.setattr(inverse, "sympy_keeps_its_size", unused)
    inverse.rearranged.cache_clear()
    inverse.keeps_its_size.cache_clear()
    try:
        for (expression, result, unknown), solution in kept_rearrangements().items():
            assert inverse.rearranged(expression, result, unknown) == solution
        for (solution, result), keeps in kept_sizes().items():
            assert inverse.keeps_its_size(solution, result) is keeps
    finally:
        inverse.rearranged.cache_clear()
        inverse.keeps_its_size.cache_clear()


def test_an_expression_the_table_lacks_is_solved_by_sympy() -> None:
    assert inverse.rearranged("work_done_by_the_tests/force_in_the_tests", "w9", "x9") is None
    assert inverse.rearranged("a9*b9", "c9", "b9") == "c9/a9"
    assert inverse.keeps_its_size("c9/a9", "c9") is True
