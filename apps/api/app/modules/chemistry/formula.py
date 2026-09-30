"""Formula text: the conventional order of the elements in a written formula."""

from __future__ import annotations

from app.modules.chemistry.elements import BY_SYMBOL

# Hydrogen is written after these when it bonds to them (NH3, PH3, AsH3), not before as in
# H2O or HCl.
_HYDRIDE_HEADS = frozenset({"N", "P", "As", "Sb"})


def _en(symbol: str) -> float:
    element = BY_SYMBOL.get(symbol)
    if element is None or element.electronegativity is None:
        return 99.0  # noble gases and unknown symbols go last
    return element.electronegativity


def _order(counts: dict[str, int]) -> list[str]:
    symbols = list(counts)
    if "C" in counts:
        # Hill system: carbon, hydrogen, then the rest alphabetically.
        rest = sorted(symbol for symbol in symbols if symbol not in {"C", "H"})
        return ["C", *(["H"] if "H" in counts else []), *rest]
    # No carbon: the more electropositive element first (NaCl, Fe2O3, H2SO4), by
    # electronegativity, with the hydrogen of NH3-type hydrides written last.
    ordered = sorted(symbols, key=lambda symbol: (_en(symbol), symbol))
    if "H" in counts and _HYDRIDE_HEADS & set(counts):
        ordered.remove("H")
        ordered.append("H")
    return ordered


def hill_formula(counts: dict[str, int]) -> str:
    """``{"O": 1, "C": 1, "H": 2}`` → ``CH2O``; ``{"Cl": 1, "Na": 1}`` → ``NaCl``."""
    return "".join(
        symbol if counts[symbol] == 1 else f"{symbol}{counts[symbol]}"
        for symbol in _order(counts)
        if counts[symbol]
    )
