"""Exact values on a coordinate plane written as a textbook prints them."""

from __future__ import annotations

from fractions import Fraction

_MINUS = "\u2212"
_PRIME = "\u2032"


def coordinate_text(value: Fraction) -> str:
    """3, -2, 2.5, 1/3: a whole number or a short decimal as it is, else a fraction."""
    sign = _MINUS if value < 0 else ""
    value = abs(value)
    if value.denominator == 1:
        return f"{sign}{value.numerator}"
    for places in (1, 2, 3):
        scaled = value * 10**places
        if scaled.denominator == 1:
            return f"{sign}{float(value):.{places}f}"
    return f"{sign}{value.numerator}/{value.denominator}"


def pair_text(point: tuple[Fraction, Fraction]) -> str:
    return f"({coordinate_text(point[0])}, {coordinate_text(point[1])})"


def point_label(name: str, point: tuple[Fraction, Fraction]) -> str:
    """A stated point: its letter and its coordinates, "A(1, 2)", or "(1, 2)" unnamed."""
    return f"{name.strip()}{pair_text(point)}"


def primed(name: str, times: int) -> str:
    """A point's image after ``times`` transformations: A', A''; an unnamed point stays so."""
    base = name.strip().rstrip("'\u2032\u2033")
    if not base:
        return ""
    return base + ("\u2033" if times == 2 else _PRIME * times)


def primes(name: str) -> int:
    """How many primes a stated name carries (A' and A' are one, A'' two)."""
    tail = name.strip()[1:]
    return tail.count("'") + tail.count(_PRIME) + 2 * tail.count("\u2033")
