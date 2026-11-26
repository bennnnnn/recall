"""Every physics reader of a mass or a speed reads the one table (audit, 2026-11-25).

Ten extractors kept their own mass and speed lists and they disagreed: the tension reader
had no grams, so "a 500 g mass hangs from a rope" was no question; only gravitation read
tonnes. The display's spelled units were a fourth copy of the length and time tables.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.modules.physics.display import plain_unit
from app.services.unit_text import LENGTH_UNITS, MASS_UNITS, TIME_UNITS

_EXTRACTORS = Path(__file__).resolve().parents[3] / "modules" / "physics" / "extractors"
_SETTINGS = Settings(math_tools_enabled=True)


def _answer(question: str) -> str | None:
    intent = extract_physics_intent(question)
    block = None if intent is None else build_verified_physics_block(intent, _SETTINGS)
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("A 500 g mass hangs from a rope. Find the tension in the rope.", "4.91 N"),
        ("A 2 kg mass hangs from a rope. Find the tension in the rope.", "19.62 N"),
    ],
)
def test_a_mass_in_any_unit_is_read(question: str, answer: str) -> None:
    assert _answer(question) == answer


def test_no_extractor_keeps_its_own_mass_or_speed_list() -> None:
    own_list = re.compile(r"kg\|(?:g|mg|lbs?|tonnes?|grams?)\b|m/s\|km/h")
    for path in _EXTRACTORS.glob("*.py"):
        if path.name == "unit_patterns.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "VALUE_UNIT_RE" in line or path.name == "stated_values.py":
                continue  # the generic value reader lists every unit, not a mass's
            assert own_list.search(line) is None, f"{path.name}:{number}: {line.strip()}"


@pytest.mark.parametrize(
    "table", [LENGTH_UNITS, TIME_UNITS, MASS_UNITS], ids=["length", "time", "mass"]
)
def test_the_display_writes_the_tables_symbols(table: dict[str, str]) -> None:
    for spelling, symbol in table.items():
        if symbol == "day":  # a word is written as typed: "7.21 days"
            assert plain_unit(spelling) == spelling
            continue
        assert plain_unit(spelling) == plain_unit(symbol), spelling
