"""The kept rearrangements (``law_binding/rearrangements.json``): what the catalog asks,
and SymPy's answer to each.

``uv run python -m app.tests.modules.physics.rearrangement_table`` writes the file again
after a law's arithmetic changes. It takes about half a minute.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from app.modules.physics.catalog import CATALOG
from app.services.law_binding.inverse import sympy_keeps_its_size, sympy_rearranged
from app.services.law_binding.rearrangements import TABLE_PATH
from app.services.law_binding.spec import FormulaSpec, result_variable

Key = tuple[str, str, str]
SizeKey = tuple[str, str]


def asked_by(spec: FormulaSpec) -> tuple[list[Key], bool]:
    """Every (expression, result, input) ``inverse.rearranged`` can be asked for this law,
    and whether its answers' sizes are asked too (``inverse_of``): each form of the law,
    solved for each input a question can ask."""
    stated = result_variable(spec)
    binding = spec.binding
    if stated is None or binding is None or binding.negative_detail:
        return [], False
    written = (spec.expression, *(variant.expression for variant in spec.variants))
    forms = sorted({form for form in written if form is not None})
    inputs = sorted({variable.name for variable in spec.variables if variable.visible})
    keys = [(form, stated.name, name) for form in forms for name in inputs]
    return keys, not binding.nonnegative


def asked() -> dict[str, tuple[list[Key], bool]]:
    """``asked_by`` for each law of the catalog that asks any."""
    found = {spec.id: asked_by(spec) for spec in CATALOG.values()}
    return {law: rows for law, rows in found.items() if rows[0]}


def worked_out(keys: list[Key], sizes: bool) -> tuple[dict[Key, str | None], dict[SizeKey, bool]]:
    """SymPy's answer to each key, and to each solution's size when ``sizes``."""
    solutions = {key: sympy_rearranged(*key) for key in keys}
    kept: dict[SizeKey, bool] = {}
    for (_form, result, _name), solution in solutions.items():
        if sizes and solution is not None:
            kept[(solution, result)] = sympy_keeps_its_size(solution, result)
    return solutions, kept


def table_text(solutions: dict[Key, str | None], sizes: dict[SizeKey, bool]) -> str:
    """The file's text: one row a line, sorted, so a change reads as a short diff."""

    def rows(entries: Sequence[Sequence[object]]) -> str:
        return ",\n".join(f"    {json.dumps(row, ensure_ascii=False)}" for row in entries)

    rearranged = sorted([*key, solution] for key, solution in solutions.items())
    kept = sorted([*key, keeps] for key, keeps in sizes.items())
    return (
        "{\n"
        f'  "rearranged": [\n{rows(rearranged)}\n  ],\n'
        f'  "keeps_its_size": [\n{rows(kept)}\n  ]\n'
        "}\n"
    )


def main() -> None:
    solutions: dict[Key, str | None] = {}
    sizes: dict[SizeKey, bool] = {}
    for keys, sized in asked().values():
        found, kept = worked_out(keys, sized)
        solutions.update(found)
        sizes.update(kept)
    TABLE_PATH.write_text(table_text(solutions, sizes), encoding="utf-8")
    print(f"{len(solutions)} rearrangements, {len(sizes)} sizes -> {TABLE_PATH}")


if __name__ == "__main__":
    main()
