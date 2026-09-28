"""School coordination formulas such as ``[Co(NH3)6]Cl3``.

Crystal-field splitting and molecular-orbital diagrams stay model-only.
Ligands are a fixed monodentate/bidentate table, not a general namer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# token, name, charge, donor atoms
_LIGANDS: tuple[tuple[str, str, int, int], ...] = (
    ("NH3", "ammine", 0, 1),
    ("H2O", "aqua", 0, 1),
    ("NO2", "nitrito", -1, 1),
    ("CN", "cyanido", -1, 1),
    ("OH", "hydroxido", -1, 1),
    ("CO", "carbonyl", 0, 1),
    ("Cl", "chlorido", -1, 1),
    ("Br", "bromido", -1, 1),
    ("F", "fluorido", -1, 1),
    ("I", "iodido", -1, 1),
    ("en", "ethylenediamine", 0, 2),
)
_PREFIX = {1: "", 2: "di", 3: "tri", 4: "tetra", 5: "penta", 6: "hexa"}
_COUNTER_NAMES = {
    "Cl": "chloride",
    "Br": "bromide",
    "F": "fluoride",
    "I": "iodide",
    "CN": "cyanide",
    "NO3": "nitrate",
    "SO4": "sulfate",
    "K": "potassium",
    "Na": "sodium",
    "NH4": "ammonium",
}
_COUNTER_CHARGE = {
    "Cl": -1,
    "Br": -1,
    "F": -1,
    "I": -1,
    "CN": -1,
    "NO3": -1,
    "SO4": -2,
    "K": 1,
    "Na": 1,
    "NH4": 1,
}
_COMPLEX_RE = re.compile(
    r"^(?P<left>[A-Z][a-z]?\d*)?\[(?P<inside>.+)\](?P<right>[A-Z][A-Za-z0-9]*\d*)?$"
)


@dataclass(frozen=True)
class CoordinationComplex:
    metal: str
    oxidation_state: int
    coordination_number: int
    name: str


def _split_ligands(inside: str) -> list[tuple[str, int]] | None:
    found: list[tuple[str, int]] = []
    index = 0
    tokens = sorted(_LIGANDS, key=lambda item: len(item[0]), reverse=True)
    while index < len(inside):
        if inside[index] == "(":
            end = inside.find(")", index)
            if end < 0:
                return None
            token = inside[index + 1 : end]
            index = end + 1
        else:
            token = next((name for name, *_rest in tokens if inside.startswith(name, index)), "")
            if not token:
                return None
            index += len(token)
        count_digits = ""
        while index < len(inside) and inside[index].isdigit():
            count_digits += inside[index]
            index += 1
        found.append((token, int(count_digits or "1")))
    return found


def _counter(text: str | None) -> tuple[str, int, int] | None:
    if not text:
        return "", 0, 0
    match = re.match(r"^([A-Z][a-z]?\d*)(\d*)$", text)
    if match is None:
        return None
    # Trailing digits on the whole counter, not inside NH4 or NO3.
    for known in sorted(_COUNTER_CHARGE, key=len, reverse=True):
        if text.startswith(known):
            rest = text[len(known) :]
            count = int(rest) if rest else 1
            return _COUNTER_NAMES[known], _COUNTER_CHARGE[known] * count, count
    return None


def parse_coordination(formula: str) -> CoordinationComplex | None:
    """Oxidation state, coordination number, and a simple additive name."""
    match = _COMPLEX_RE.match(formula.replace(" ", ""))
    if match is None:
        return None
    body = match.group("inside")
    metal_match = re.match(r"^([A-Z][a-z]?)", body)
    if metal_match is None:
        return None
    metal = metal_match.group(1)
    if any(metal == name for name, *_rest in _LIGANDS):
        return None
    ligands = _split_ligands(body[len(metal) :])
    if not ligands:
        return None
    table = {name: (label, charge, donors) for name, label, charge, donors in _LIGANDS}
    if any(token not in table for token, _count in ligands):
        return None
    left = _counter(match.group("left"))
    right = _counter(match.group("right"))
    if left is None or right is None:
        return None
    _left_name, left_charge, _left_count = left
    right_name, right_charge, _right_count = right
    complex_charge = -(left_charge + right_charge)
    ligand_charge = sum(table[token][1] * count for token, count in ligands)
    coordination = sum(table[token][2] * count for token, count in ligands)
    oxidation = complex_charge - ligand_charge
    parts = []
    for token, count in sorted(ligands, key=lambda item: table[item[0]][0]):
        prefix = _PREFIX.get(count)
        if prefix is None:
            return None
        parts.append(f"{prefix}{table[token][0]}")
    roman = _roman(oxidation)
    if roman is None:
        return None
    ate = {
        "Fe": "ferrate",
        "Cu": "cuprate",
        "Ag": "argentate",
        "Au": "aurate",
        "Co": "cobaltate",
    }
    metal_names = {
        "Co": "cobalt",
        "Fe": "iron",
        "Cu": "copper",
        "Ni": "nickel",
        "Cr": "chromium",
        "Mn": "manganese",
        "Zn": "zinc",
        "Ag": "silver",
        "Pt": "platinum",
    }
    if complex_charge < 0:
        metal_name = ate.get(metal, f"{metal_names.get(metal, metal.lower())}ate")
    elif right_name:
        metal_name = metal_names.get(metal, metal.lower())
    else:
        metal_name = metal_names.get(metal, metal)
    complex_name = f"{''.join(parts)}{metal_name}({roman})"
    if left and left[0]:
        complex_name = f"{left[0]} {complex_name}"
    if right_name:
        complex_name = f"{complex_name} {right_name}"
    return CoordinationComplex(metal, oxidation, coordination, complex_name)


def _roman(value: int) -> str | None:
    names = {0: "0", 1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
    if value < 0:
        mapped = names.get(-value)
        return None if mapped is None else f"-{mapped}"
    return names.get(value)
