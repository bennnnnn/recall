"""School homework helpers (complex, units, trig) — not geometry/calc I."""

from __future__ import annotations

from app.services.math import school as math_school


def test_imaginary_unit_mapping_skips_sin_and_pi() -> None:
    assert math_school._imaginary_unit_to_sympy("3+4i") == "3+4I"
    assert math_school._imaginary_unit_to_sympy("3+4j") == "3+4I"
    assert math_school._imaginary_unit_to_sympy("2+3i*sin(30)") == "2+3I*sin(30)"
    assert math_school._imaginary_unit_to_sympy("sin(pi)+i") == "sin(pi)+I"


def test_evaluate_complex_plain() -> None:
    assert math_school.evaluate_complex("3+4i") == "3 + 4 i"
    assert math_school.evaluate_complex("3+4j") == "3 + 4 i"


def test_evaluate_complex_keeps_sin() -> None:
    """Regression: naive ``i``→``I`` replace turned ``sin`` into ``sIn``."""
    out = math_school.evaluate_complex("2+3i*sin(30)")
    assert "sIn" not in out
    assert r"\sin" in out
    assert "i" in out


def test_evaluate_complex_keeps_pi() -> None:
    out = math_school.evaluate_complex("2+3i*sin(pi/6)")
    assert "pI" not in out


def test_solve_ode_builds_eq_not_parse_string() -> None:
    out = math_school.solve_ode("dy/dx = y")
    assert out.solved
    low = out.latex.lower()
    assert "e" in low or "exp" in low


def test_solve_ode_yprime() -> None:
    out = math_school.solve_ode("y' = -2*y")
    assert out.solved
    assert "2" in out.latex or "e" in out.latex.lower()


def test_percent_change_and_percent_is() -> None:
    assert math_school.percent_increase(200, 12) == "224"
    assert math_school.percent_decrease(200, 12) == "176"
    assert math_school.percent_is(12, 50) == "24"


def test_split_ratio_two_and_three_parts() -> None:
    assert math_school.split_ratio(120, [2, 3]) == "48:72"
    assert math_school.split_ratio(100, [2, 3, 5]) == "20:30:50"


def test_sequence_ap_gp_and_mixed_refused() -> None:
    assert math_school.sequence_nth([3, 7, 11, 15], 10) == "39"
    assert math_school.sequence_sum([3, 7, 11, 15], 10) == "210"
    assert math_school.sequence_nth([2, 4, 8, 16], 5) == "32"
    assert math_school.sequence_sum([2, 4], 20) == "420"
    assert math_school.is_ap_or_gp([1, 2, 4, 7]) is False


def test_critical_points_cubic() -> None:
    out = math_school.critical_points("x**3 - 3*x")
    assert out.solved
    assert "1" in out.latex
    assert "-1" in out.latex
