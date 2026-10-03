# ruff: noqa: RUF002 -- docstrings show the multiplication sign the reader sees.
"""Complete literal physics requests may display their existing verified result.

The stored intent is checked against a fresh extraction of the user text.
The reply reads the solver's formula and substitution; it does not parse them
back out of the prompt line.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from app.models.schemas.physics import PhysicsIntent
from app.models.schemas.physics.simulation import SIMULATION_SPEC_TYPES
from app.modules.physics.catalog import (
    formula_spec,
    select_formula,
    symbol_for,
    variable_for,
    visible_assumptions,
)
from app.modules.physics.display import is_conversion_row, latex_given, latex_unit, si_symbol
from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.solvers.common import _PARAM_SI_DIMENSIONS, _to_si
from app.modules.physics.working import result_symbol_for
from app.services.chat.presentation import present_assistant_markdown
from app.services.solving import SolveServiceError, VerifiedPhysicsBlock

_EXTRA_REQUEST = re.compile(
    r"\b(?:hint|air resistance|(?<!stokes )(?<!stokes' )drag|wind|"
    r"convert the answer|convert (?:it|this|that))\b"
    r"|\b(?:and|also|then)\s+(?:solve|calculate|compute|find|convert|explain|show|tell)\b",
    re.IGNORECASE,
)


def _expected_trajectory_type(intent: PhysicsIntent) -> str:
    """The one ``trajectory_type`` ``solve_physics`` emits for this intent.

    Must stay in lockstep with ``solve_kinematics`` / ``solve_projectile``. This
    guard exists to prove the fence came from that solve rather than from the
    model, so an extra value here would be a hole — and a missing one silently
    drops the whole direct reply, which is the harder failure to notice.
    """
    if intent.kind == "projectile":
        return "parametric"
    if intent.kind == "suvat":
        if intent.physics_op == "suvat_distance" or (
            intent.physics_op == "suvat_time" and "d" in (intent.physics_params or {})
        ):
            return "position_vs_time"
        return "velocity_vs_time"
    if intent.physics_op in ("velocity", "speed"):
        return "velocity_vs_time"
    return "position_vs_time"


def can_direct_physics(
    verified: VerifiedPhysicsBlock, text: str, fences: list[dict[str, Any]]
) -> bool:
    intent = verified.physics_intent
    if intent is None:
        return False
    # The answer fence carries the typeset card; the plain answer is for guards.
    answer = verified.display_answer or verified.canonical_answer
    # P14 attaches a scene alongside the trajectory graph, so a projectile
    # carries two fences where the rule below expects one. A scene is not a
    # second answer — it is an illustration of the same one, server-owned and
    # never model-written — so it is set aside before the count rather than
    # counted. Without this, adding the scene silently switched every
    # projectile back to the provider path: this returned False, the
    # pre-computed reply was dropped, and nothing anywhere reported it.
    answering = [f for f in fences if f.get("type") not in SIMULATION_SPEC_TYPES]
    if not answer or len(answer) > 800 or len(answering) != 1:
        return False
    if not verified.physics_working:
        return False
    fence = answering[0]
    actual = extract_physics_intent(text)
    if actual is None or _EXTRA_REQUEST.search(text):
        return False
    if actual.model_dump() != intent.model_dump():
        return False
    if fence.get("type") == "answer":
        return fence.get("type") == "answer" and fence.get("content") == answer
    if fence.get("type") != "trajectory" or fence.get("expr2") or fence.get("points2"):
        return False
    points = fence.get("points")
    return bool(
        isinstance(points, list)
        and len(points) >= 2
        and all(
            isinstance(point, list)
            and len(point) == 2
            and all(type(value) in {int, float} and math.isfinite(value) for value in point)
            for point in points
        )
        and all(
            type(fence.get(key)) in {int, float} and math.isfinite(fence[key])
            for key in ("x_min", "x_max")
        )
        and fence["x_min"] < fence["x_max"]
        and fence.get("trajectory_type") == _expected_trajectory_type(actual)
    )


def _parameter_symbol(name: str, operation: str) -> str:
    """Display symbol declared on this operation. The raw name is not a symbol."""
    spec = formula_spec(operation)
    if spec is None:
        raise ValueError(f"no physics formula named {operation}")
    symbol = symbol_for(spec, name)
    if symbol is None:
        raise ValueError(f"{operation} does not declare {name}")
    return symbol


def _formula_identity(formula: str) -> str:
    """Ignore presentation-only multiplication dots when comparing laws."""
    return formula.replace(r"\cdot", "").replace(" ", "")


def _formula_rows(intent: PhysicsIntent, formulas: list[str]) -> list[str]:
    """Name the governing law, show its base form, then any rearrangement."""
    operation = intent.physics_op or ""
    spec = formula_spec(operation)
    name = spec.law_name if spec is not None else "Physics formula"
    params = intent.physics_params or {}
    base: str | None = None
    lines: tuple[str, ...] = ()
    if spec is not None:
        base, lines, _assumptions = select_formula(spec, params)
    if lines:
        return [f"{name}:", *[f"${line}$" for line in lines]]
    rows = [f"{name}:"]
    if base is None:
        rows.extend(f"${formula}$" for formula in formulas)
        return rows

    rows.append(f"${base}$")
    base_lhs = base.split(" = ", 1)[0].strip()
    for formula in formulas:
        formula_lhs = formula.split(" = ", 1)[0].strip()
        if _formula_identity(formula) == _formula_identity(base):
            continue
        if formula_lhs == base_lhs:
            rows.append("Equivalent form for the given quantities:")
        else:
            rows.append(f"Rearranged for ${formula_lhs}$:")
        rows.append(f"${formula}$")
    return rows


def _given_value(name: str, value: float, unit: str, substitution: str) -> str:
    """The value as written and, when that is not SI, the value the solver used.

    A substitution in SI numbers needs the step that produced them first:
    500 nm = 5 × 10⁻⁷ m. A solver that works in the written units (150 km in
    2 h) needs none, and neither do angles or rpm, whose formula converts.
    """
    written = f"{latex_given(value)}{latex_unit(unit)}"
    dimension = _PARAM_SI_DIMENSIONS.get(name)
    if (
        not unit
        or dimension in (None, "dimensionless", "revolution / minute")
        or name.startswith("angle")
        # Written into the arithmetic as typed: "4 µF", not the "4 µF" ending "2.4 µF".
        or re.search(rf"(?<![\d.]){re.escape(written)}", substitution) is not None
    ):
        return written
    try:
        si_value = _to_si(value, unit, expected_key=name)
    except SolveServiceError:
        return written
    si_unit = si_symbol(dimension)
    if latex_unit(si_unit) == latex_unit(unit) and math.isclose(si_value, value):
        return written
    return f"{written} = {latex_given(si_value)}{latex_unit(si_unit)}"


def format_direct_physics_working(verified: VerifiedPhysicsBlock) -> str | None:
    """Five-section worked layout for a solver-verified instant reply.

    This formats the intent and the formula and substitution the solver stored.
    It never derives a result. The answer remains the canonical answer fence
    appended by the generic direct formatter.
    """
    intent = verified.physics_intent
    if intent is None or not verified.physics_working:
        return None
    if not verified.physics_formulas or not verified.physics_substitutions:
        return None

    params = intent.physics_params or {}
    units = intent.physics_units or {}
    given_rows: list[str] = []
    # The arithmetic only: a conversion row restates the answer, and an answer equal to a
    # given (λ = d in Bragg's law at 30°) would read as that given written into the working.
    arithmetic = " ".join(
        row for row in verified.physics_substitutions if not is_conversion_row(row)
    )
    operation = intent.physics_op or ""
    given_spec = formula_spec(operation)
    for name, value in params.items():
        variable = variable_for(given_spec, name) if given_spec is not None else None
        if variable is not None and not variable.visible:
            continue
        symbol = _parameter_symbol(name, operation)
        shown = _given_value(name, value, units.get(name, ""), arithmetic)
        given_rows.append(f"${symbol} = {shown}$")

    formulas = list(verified.physics_formulas)
    substitutions = list(verified.physics_substitutions)
    result_symbol = result_symbol_for(intent)
    find_symbol = result_symbol or formulas[0].split(" = ", 1)[0]
    rows = ["**Given**", *given_rows, "**Find**", f"${find_symbol}$", "**Formula**"]
    rows.extend(_formula_rows(intent, formulas))
    spec = formula_spec(intent.physics_op or "")
    if spec is not None:
        rows.extend(
            f"Assumption: {assumption}." for assumption in visible_assumptions(spec, params)
        )
    rows.append("**Substitution**")
    rows.extend(f"${substitution}$" for substitution in substitutions)
    rows.append("**Answer**")
    return "\n\n".join(rows)


def _solver_fences(verified: VerifiedPhysicsBlock) -> list[dict[str, Any]]:
    fences: list[dict[str, Any]] = []
    for fence in (verified.canonical_fence, *verified.canonical_fences):
        if fence is not None and fence not in fences:
            fences.append(fence)
    return fences


def maybe_direct_physics_reply(
    verified: VerifiedPhysicsBlock | None,
    user_text: str,
    *,
    has_image_attachment: bool = False,
) -> str | None:
    """Render a complete physics reply from solver-owned data only."""
    if verified is None or has_image_attachment:
        return None
    fences = _solver_fences(verified)
    if not can_direct_physics(verified, user_text, fences):
        return None
    working = format_direct_physics_working(verified)
    if working is None:
        return None
    answer = (verified.display_answer or verified.canonical_answer or "").strip()
    if not answer:
        return None
    parts = [working, f"```answer\n{answer}\n```"]
    for fence in fences:
        fence_type = fence.get("type")
        if fence_type == "answer":
            continue
        language = "simulation" if fence_type in SIMULATION_SPEC_TYPES else "graph"
        parts.append(f"```{language}\n{json.dumps(fence, separators=(',', ':'))}\n```")
    reply = "\n\n".join(parts) + "\n"
    intent = verified.physics_intent
    if (
        intent is not None
        and intent.kind == "kinematics"
        and intent.physics_op
        in {
            "velocity",
            "acceleration",
        }
    ):
        return present_assistant_markdown(f"Upward is positive.\n\n{reply}")
    return present_assistant_markdown(reply)
