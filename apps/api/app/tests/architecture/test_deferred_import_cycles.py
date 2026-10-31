"""A cycle through deferred imports may only shrink.

``test_import_cycles`` allows no cycle among the imports that run at load time. An
import deferred into a function fixes the load order but leaves the dependency: the two
modules still need each other. Counting those imports too, today's cycles are recorded
in ``import_cycle_baseline.json``: each one's modules and how many imports run between
them. No new cycle may form, none may take in more modules or more imports, and two may
not join. The fix for a cycle is shared code moved below both modules, not another
deferred import.

When a cycle shrinks, or a module in one is renamed or moved (the same number of modules,
no more imports), rerun with ``UPDATE_IMPORT_CYCLES=1``: it records the cycles as they
are and prints each changed one. It never records a larger cycle.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from functools import cache
from pathlib import Path

from .boundary_support import _import_cycles, _import_graph, _module_imports

_BASELINE = Path(__file__).with_name("import_cycle_baseline.json")


@dataclass(frozen=True)
class _Cycle:
    modules: list[str]
    imports: int


def _cycles_of(graph: dict[str, set[str]]) -> list[_Cycle]:
    """Each cycle's modules, and the imports that run between them."""
    cycles = []
    for members in sorted(_import_cycles(graph)):
        inside = set(members)
        cycles.append(_Cycle(members, sum(len(graph[module] & inside) for module in members)))
    return cycles


@cache
def _cycles() -> tuple[_Cycle, ...]:
    """Modules that reach one another through any import that can run."""
    return tuple(_cycles_of(_import_graph(_module_imports(load_time=False, runtime=True))))


def _changed_home(cycle: _Cycle, home: _Cycle) -> tuple[str | None, str | None]:
    """(how ``cycle`` grew past its recorded ``home``, how it changed without growing)."""
    size = len(home.modules)
    gained = sorted(set(cycle.modules) - set(home.modules))
    if len(cycle.modules) > size:
        return f"the cycle of {size} grew to {len(cycle.modules)}, taking in " + ", ".join(
            gained
        ), None
    if cycle.imports > home.imports:
        return (
            f"the cycle of {size} holding {home.modules[0]} has {cycle.imports} imports among"
            f" its modules, {home.imports} recorded"
        ), None
    if gained:
        lost = sorted(set(home.modules) - set(cycle.modules))
        return (
            None,
            f"the cycle of {size} now holds {', '.join(gained)} instead of {', '.join(lost)}",
        )
    if cycle != home:
        return None, (
            f"the cycle of {size} holding {home.modules[0]} is down to {len(cycle.modules)}"
            f" modules and {cycle.imports} imports"
        )
    return None, None


def _compare(cycles: tuple[_Cycle, ...], recorded: list[_Cycle]) -> tuple[list[str], list[str]]:
    """(cycles that grew, cycles that changed without growing)."""
    grown: list[str] = []
    changed: list[str] = []
    for cycle in cycles:
        homes = [known for known in recorded if set(cycle.modules) & set(known.modules)]
        if not homes:
            grown.append(f"a new cycle of {len(cycle.modules)}: " + ", ".join(cycle.modules))
        elif len(homes) > 1:
            sizes = " and ".join(str(len(known.modules)) for known in homes)
            grown.append(
                f"a cycle of {len(cycle.modules)} joins modules of the recorded cycles of"
                f" {sizes}: " + ", ".join(cycle.modules)
            )
        else:
            growth, change = _changed_home(cycle, homes[0])
            grown.extend([growth] if growth else [])
            changed.extend([change] if change else [])
    current = [set(cycle.modules) for cycle in cycles]
    for known in recorded:
        if not any(members & set(known.modules) for members in current):
            changed.append(f"the cycle of {len(known.modules)} holding {known.modules[0]} is gone")
    return grown, changed


def _recorded(cycles: tuple[_Cycle, ...]) -> list[_Cycle]:
    recorded = [_Cycle(**entry) for entry in json.loads(_BASELINE.read_text())]
    grown, changed = _compare(cycles, recorded)
    if os.environ.get("UPDATE_IMPORT_CYCLES") and not grown and changed:
        print("recorded import cycles that changed without growing:\n  " + "\n  ".join(changed))
        recorded = list(cycles)
        _BASELINE.write_text(json.dumps([asdict(cycle) for cycle in recorded], indent=2) + "\n")
    return recorded


def test_compare_names_grown_and_changed_cycles() -> None:
    recorded = [_Cycle(["a", "b", "c"], 3), _Cycle(["d", "e"], 2)]
    assert _compare((_Cycle(["a", "b", "c"], 3), _Cycle(["d", "e"], 2)), recorded) == ([], [])
    assert _compare((_Cycle(["x", "y"], 2),), recorded)[0] == ["a new cycle of 2: x, y"]
    assert _compare((_Cycle(["a", "b", "c", "z"], 4),), recorded)[0] == [
        "the cycle of 3 grew to 4, taking in z"
    ]
    assert _compare((_Cycle(["a", "b", "c"], 4),), recorded)[0] == [
        "the cycle of 3 holding a has 4 imports among its modules, 3 recorded"
    ]
    assert _compare((_Cycle(["c", "d"], 2),), recorded)[0] == [
        "a cycle of 2 joins modules of the recorded cycles of 3 and 2: c, d"
    ]
    renamed = _compare((_Cycle(["a", "b", "c2"], 3), _Cycle(["d", "e"], 2)), recorded)
    assert renamed == ([], ["the cycle of 3 now holds c2 instead of c"])
    assert _compare((_Cycle(["a", "b"], 2),), recorded) == (
        [],
        [
            "the cycle of 3 holding a is down to 2 modules and 2 imports",
            "the cycle of 2 holding d is gone",
        ],
    )


def test_no_deferred_import_cycle_forms_or_grows() -> None:
    cycles = _cycles()
    grown, _ = _compare(cycles, _recorded(cycles))
    assert grown == [], (
        "the import graph got more tangled. Move the code both modules need into a module"
        " below them instead of deferring an import; UPDATE_IMPORT_CYCLES=1 never records"
        " growth.\n  " + "\n  ".join(grown)
    )


def test_the_recorded_cycles_are_current() -> None:
    cycles = _cycles()
    _, changed = _compare(cycles, _recorded(cycles))
    assert changed == [], (
        "the cycles changed without growing (smaller, or a module renamed or moved): rerun"
        " this test with UPDATE_IMPORT_CYCLES=1 to record them.\n  " + "\n  ".join(changed)
    )
