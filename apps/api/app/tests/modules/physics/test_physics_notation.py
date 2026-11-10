"""A worked reply writes a British-style school textbook's letters: s is a displacement, d a
distance, u an initial velocity and v a final one (v = u + at, v² = u² + 2as)."""

from __future__ import annotations

import re

import pytest

from app.core.config import Settings
from app.modules.physics.catalog import CATALOG, symbol_for
from app.modules.physics.direct import format_direct_physics_working
from app.modules.physics.notation import _SHOWN, shown
from app.modules.physics.reply_policy import PHYSICS_SYMBOLS, physics_prompt_hints
from app.services.law_binding.spec import FormulaSpec
from app.tests.modules.physics.support import build_verified_physics_block, extract_physics_intent


@pytest.mark.parametrize(
    "operation, written, expected",
    [
        ("impulse", "I = m(v_2 - v_1)", "I = m(v - u)"),
        (
            "work_energy",
            r"W_{net} = \frac{1}{2}m(v_2^2 - v_1^2)",
            r"W_{net} = \frac{1}{2}m(v^2 - u^2)",
        ),
        ("final_velocity", r"v_1',\ v_2'", r"v_1,\ v_2"),
        (
            "final_velocity",
            r"m_1v_1 + m_2v_{2} = (m_1+m_2)v_f",
            r"m_1u_1 + m_2u_2 = (m_1+m_2)v",
        ),
        ("stopping_distance", r"d_b = \frac{v^2}{2a}", r"d_b = \frac{u^2}{2a}"),
        ("time_to_peak", r"t_{\text{top}} = \frac{v_0}{g}", r"t_{\text{top}} = \frac{u}{g}"),
        ("position", r"h = h_0 + v_0 t - \frac{1}{2} g t^2", r"h = h_0 + u t - \frac{1}{2} g t^2"),
        ("range", r"R = \frac{v_0^2 \sin(2\theta)}{g}", r"R = \frac{u^2 \sin(2\theta)}{g}"),
        # Units, words and commands are not symbols.
        ("impulse", r"v_2 = 14\,\mathrm{m/s}", r"v = 14\,\mathrm{m/s}"),
        ("impulse", r"v_1 \text{ value}", r"u \text{ value}"),
        ("stopping_distance", r"\varepsilon \vec{v}", r"\varepsilon \vec{u}"),
    ],
)
def test_shown_writes_initial_and_final_velocity(
    operation: str, written: str, expected: str
) -> None:
    assert shown(written, operation) == expected


@pytest.mark.parametrize(
    "operation, written",
    [
        # The constant-acceleration laws are written in u, v and s already.
        ("suvat_velocity", "v = u + at"),
        ("suvat_distance", r"s = ut + \tfrac{1}{2}at^2"),
        # A plain speed has no start or end: v = d/t stays v.
        ("rate_speed", r"v = \frac{d}{t}"),
        ("momentum", "p = mv"),
        ("mirror_focal_length", r"\frac{1}{f} = \frac{1}{d_o} + \frac{1}{d_i}"),
        (None, "v = v_0 + at"),
    ],
)
def test_shown_leaves_other_laws_as_written(operation: str | None, written: str) -> None:
    assert shown(written, operation) == written


def _catalog_latex(spec: FormulaSpec) -> list[str]:
    rows = [spec.base_latex or ""]
    for variant in spec.variants:
        rows.extend((variant.latex or "", *variant.lines, variant.result_symbol or ""))
    return [row for row in rows if row]


# What a school book never writes for a start or an end: v_i, v_f, v_0, or a velocity
# numbered before and after a collision (v_1, v_2 of one body).
_OLD_SYMBOL = re.compile(r"v_(?:[if0]|\{[if0]\}|\{[12][if]\})(?![A-Za-z0-9}])")


@pytest.mark.parametrize("operation", sorted(CATALOG))
def test_no_law_shows_v_i_v_f_or_v_0(operation: str) -> None:
    """Every catalog law, as the reply shows it, keeps to u and v. A law the drag model
    writes with v_0 (a university course's) is the one exception."""
    spec = CATALOG[operation]
    if spec.kind == "fluids":
        return
    rows = [shown(row, operation) for row in _catalog_latex(spec)]
    rows.append(shown(spec.result_symbol, operation))
    rows.extend(
        shown(symbol_for(spec, variable.name) or "", operation)
        for variable in spec.variables
        if variable.visible
    )
    assert [row for row in rows if _OLD_SYMBOL.search(row)] == []


@pytest.mark.parametrize("operation", sorted(_SHOWN))
def test_every_renamed_law_is_a_catalog_law(operation: str) -> None:
    assert operation in CATALOG


def _reply(question: str) -> str:
    intent = extract_physics_intent(question)
    assert intent is not None
    block = build_verified_physics_block(intent, Settings(math_tools_enabled=True))
    assert block is not None
    reply = format_direct_physics_working(block)
    assert reply is not None
    return reply


@pytest.mark.parametrize(
    "question, rows",
    [
        # A distance at a steady speed is d: the bus of 2026-11-10.
        (
            "A bus travels at 25 m/s. How long does it take to travel 5 km?",
            [r"$d = 5\,\mathrm{km}", "$d$ = distance", r"$v = \frac{d}{t}$"],
        ),
        # A displacement under constant acceleration is s, from u to v.
        (
            "A car accelerates uniformly from 10 m/s to 30 m/s in 5 s. What is its displacement?",
            [
                r"$u = 10\,\mathrm{m/s}$",
                r"$v = 30\,\mathrm{m/s}$",
                "where $u$ = initial velocity, $v$ = final velocity, $t$ = time",
                "**Required**  \n$s$",
                r"$s = \tfrac{1}{2}(u + v)t$",
            ],
        ),
        (
            "A car started from rest and accelerated uniformly and reached a speed of 20m/s "
            "after 5 s. What is the acceleration?",
            [
                r"$u = 0\,\mathrm{m/s}$",
                r"$v = 20\,\mathrm{m/s}$",
                "$v = u + at$",
                r"$a = \frac{v - u}{t}$",
            ],
        ),
        (
            "A ball is thrown at 10 m/s and accelerates at 3 m/s^2 over 16 m. "
            "What is its final velocity?",
            [
                "**Required**  \n$v$",
                r"$s = 16\,\mathrm{m}$",
                "$s$ = displacement",
                r"$v = \sqrt{u^2 + 2as}$",
            ],
        ),
        # Two legs walked are distances; where they leave you is a displacement.
        (
            "A man walks 3 km east and then 4 km north. What is his displacement?",
            ["**Required**  \n$s$ (displacement)", r"$s = \sqrt{d_1^2 + d_2^2}$"],
        ),
        # Work is the force times the displacement along it.
        (
            "A force of 20 N pushes a box 5 m along the floor. How much work is done?",
            [r"$s = 5\,\mathrm{m}$", "$s$ = displacement"],
        ),
        # Thrown up: the speed it leaves with is u.
        (
            "A ball is thrown vertically upward at 20 m/s. How long does it take to reach the top?",
            [r"$u = 20\,\mathrm{m/s}$", "$u$ = initial velocity", r"\frac{u}{g}$"],
        ),
    ],
)
def test_direct_reply_writes_the_textbook_letters(question: str, rows: list[str]) -> None:
    reply = _reply(question)
    for row in rows:
        assert row in reply
    assert _OLD_SYMBOL.search(reply) is None


def test_model_is_told_the_same_notation() -> None:
    assert PHYSICS_SYMBOLS in physics_prompt_hints(short=False)
    assert "$v = u + at$" in PHYSICS_SYMBOLS
    assert "displacement $s$, distance $d$" in PHYSICS_SYMBOLS
