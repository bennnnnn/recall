"""A cycle through deferred imports may only shrink.

``test_import_cycles`` allows no cycle among the imports that run at load time. An
import deferred into a function fixes the load order but leaves the dependency: the two
modules still need each other. Counting those imports too, today's cycles are recorded
in ``import_cycle_baseline.json``. No new cycle may form, no recorded one may gain a
module, and two may not join. The fix for a cycle is shared code moved below both
modules, not another deferred import. After one shrinks, rerun with
``UPDATE_IMPORT_CYCLES=1`` to record the smaller cycles.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .boundary_support import _import_cycles, _import_graph, _module_imports

_BASELINE = Path(__file__).with_name("import_cycle_baseline.json")


def _cycles() -> list[list[str]]:
    """Modules that reach one another through any import that can run."""
    return sorted(_import_cycles(_import_graph(_module_imports(load_time=False, runtime=True))))


def _widened(cycles: list[list[str]], recorded: list[list[str]]) -> list[str]:
    """Each cycle that is new, gained a module, or joins recorded cycles."""
    problems: list[str] = []
    for cycle in cycles:
        homes = [known for known in recorded if set(cycle) & set(known)]
        if not homes:
            problems.append(f"a new cycle of {len(cycle)}: " + ", ".join(cycle))
        elif len(homes) > 1:
            sizes = " + ".join(str(len(known)) for known in homes)
            problems.append(f"recorded cycles of {sizes} joined into one of {len(cycle)}")
        elif gained := sorted(set(cycle) - set(homes[0])):
            problems.append(f"the cycle of {len(homes[0])} gained " + ", ".join(gained))
    return problems


def _recorded(cycles: list[list[str]]) -> list[list[str]]:
    recorded: list[list[str]] = json.loads(_BASELINE.read_text())
    if os.environ.get("UPDATE_IMPORT_CYCLES") and not _widened(cycles, recorded):
        recorded = cycles
        _BASELINE.write_text(json.dumps(recorded, indent=2) + "\n")
    return recorded


def test_widened_names_new_grown_and_joined_cycles() -> None:
    recorded = [["a", "b", "c"], ["d", "e"]]
    assert _widened([["a", "b"], ["d", "e"]], recorded) == []
    assert _widened([["x", "y"]], recorded) == ["a new cycle of 2: x, y"]
    assert _widened([["a", "b", "c", "z"]], recorded) == ["the cycle of 3 gained z"]
    assert _widened([["a", "b", "c", "d", "e"]], recorded) == [
        "recorded cycles of 3 + 2 joined into one of 5"
    ]


def test_no_deferred_import_cycle_forms_or_grows() -> None:
    cycles = _cycles()
    widened = _widened(cycles, _recorded(cycles))
    assert widened == [], (
        "move the code both modules need below them instead of deferring an import:\n  "
        + "\n  ".join(widened)
    )


def test_the_recorded_cycles_are_current() -> None:
    cycles = _cycles()
    stale = [known for known in _recorded(cycles) if known not in cycles]
    assert stale == [], (
        f"{len(stale)} recorded cycle(s) changed: rerun with UPDATE_IMPORT_CYCLES=1 to lock in"
        " a smaller one"
    )
