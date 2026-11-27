"""The unit written after a stated number, read whole by the shared table."""

from __future__ import annotations

from app.modules.physics.givens import unit_at
from app.modules.physics.unit_runs import unit_run


def _reads_as(spelling: str, key: str) -> bool:
    from app.modules.physics.solvers.si import to_si
    from app.services.solving import SolveServiceError

    try:
        to_si(1.0, spelling, expected_key=key)
    except SolveServiceError:
        return False
    return True


def written_unit(text: str, end: int, key: str | None = None) -> str:
    """The unit written right after the number ending at ``end``; "" when none is.

    The whole unit, as the shared table reads it, so an extractor reads a prefix as the
    givens scan does: "k = 2 kN/m" was 2 N/m, "k = 500 g/s" 500 kg/s (audit 2026-11-07).
    For a slot ``key`` names, the reading of its dimension: the whole unit or the
    table's first part of it. "g = 10 N kg^-1" was read as newtons, and "ms^-2" in a g is
    m·s⁻², not a millisecond (review 2026-11-07). One nothing reads is kept as written,
    for ``to_si`` to refuse; it is never taken for the SI unit.
    """
    table = unit_at(text, end)
    run = unit_run(text, end, table)
    if key is None or run is None:
        return table[0] if table else run or ""
    for spelling in dict.fromkeys(filter(None, (run, table and table[0]))):
        if _reads_as(spelling, key):
            return spelling
    return run
