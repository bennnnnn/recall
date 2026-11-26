"""One table of element names, both spellings, read by every reader of a name.

``species_facts.ELEMENT_NAMES`` knew "aluminum" and "sulphur" but not "aluminium" or
"caesium", while three other readers kept their own spelling tables (audit, 2026-11-25).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.modules.chemistry.elements import BY_NAME
from app.modules.chemistry.nomenclature import salt_from_name
from app.modules.chemistry.species_facts import ELEMENT_NAMES, element_symbol, named_elements

_CHEMISTRY = Path(__file__).resolve().parents[3] / "modules" / "chemistry"


@pytest.mark.parametrize(
    ("name", "symbol"),
    [
        ("aluminium", "Al"),
        ("aluminum", "Al"),
        ("caesium", "Cs"),
        ("cesium", "Cs"),
        ("sulphur", "S"),
        ("sulfur", "S"),
        ("zinc", "Zn"),
    ],
)
def test_an_element_is_named_in_either_spelling(name: str, symbol: str) -> None:
    assert ELEMENT_NAMES[name] == symbol
    assert element_symbol(name.capitalize()) == symbol
    assert named_elements(f"A sample of {name} reacts.") == (symbol,)


def test_every_reader_uses_the_one_table() -> None:
    assert ELEMENT_NAMES is BY_NAME
    spelled = re.compile(r"[\"']caesium[\"']")
    owners = {
        path.relative_to(_CHEMISTRY).as_posix()
        for path in _CHEMISTRY.rglob("*.py")
        if spelled.search(path.read_text(encoding="utf-8"))
    }
    assert owners == {"elements.py"}


@pytest.mark.parametrize(
    ("name", "formula"), [("aluminium oxide", "Al2O3"), ("caesium chloride", "CsCl")]
)
def test_a_salt_is_named_in_either_spelling(name: str, formula: str) -> None:
    salt = salt_from_name(name)
    assert salt is not None and salt.formula == formula
