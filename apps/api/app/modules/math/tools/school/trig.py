"""Trigonometry extractor and verified block."""

from __future__ import annotations

import re
from dataclasses import replace

from app.core.config import Settings
from app.models.schemas.math import EquationInput, MathIntent
from app.modules.math import match as mtm
from app.modules.math import school as math_school
from app.modules.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.modules.math.tools.helpers import math_expr_or_none
from app.modules.math.tools.school._parse import _LABELED_NUMBER
from app.modules.math.tools.school.teaching import _attach_picture

_TRIG_FUNCS = ("sine", "cosine", "tangent", "sin", "cos", "tan")
_TRIG_CANON = {"sine": "sin", "cosine": "cos", "tangent": "tan"}
_TRIG_PREFIXES = (
    "find the exact value of",
    "find exact value of",
    "exact value of",
    "what is",
    "what's",
    "whats",
    "evaluate",
    "compute",
    "calculate",
    "find",
    "the value of",
    "please",
    "can you",
    "could you",
)


_DEGREE_TRIG_CALL = re.compile(
    rf"(?<![A-Za-z])(sin|cos|tan)\s*\(\s*({_LABELED_NUMBER})\s*(?:degrees?|deg|°)\s*\)",
    re.IGNORECASE,
)
_BOUNDED_DEGREE_DOMAIN = re.compile(
    rf"\bfor\s+({_LABELED_NUMBER})\s*(?:degrees?|deg|°)?\s*(<=|<|≤)\s*"
    rf"([a-zA-Z])\s*(<=|<|≤)\s*({_LABELED_NUMBER})\s*(?:degrees?|deg|°)"
    rf"(?=\s|[.?!]|$)",
    re.IGNORECASE,
)
_RADIAN_BOUND = (
    r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)?\s*\*?\s*(?:pi|π)"
    r"|[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
)
_BOUNDED_RADIAN_DOMAIN = re.compile(
    rf"\b(?:for|on)\s+({_RADIAN_BOUND})\s*(<=|<|≤)\s*"
    rf"([a-zA-Z])\s*(<=|<|≤)\s*({_RADIAN_BOUND})(?=\s|[.?!]|$)",
    re.IGNORECASE,
)


def _extract_trig_intent(cleaned: str) -> MathIntent | None:
    from app.modules.math.tools.extractors.formulas import extract_sas_area

    sas = extract_sas_area(cleaned)
    if sas is not None:
        return sas
    domain = _BOUNDED_DEGREE_DOMAIN.search(cleaned)
    if domain is not None and any(name in cleaned.lower() for name in ("sin", "cos", "tan")):
        from app.modules.math import solve as math_solve

        pairs = math_solve.try_extract_equations_from_text(cleaned)
        if len(pairs) == 1:
            lhs, rhs = pairs[0]
            return MathIntent(
                kind="trig",
                school_op="bounded_degree_equation",
                lhs=lhs,
                rhs=rhs,
                variable=domain.group(3),
                comparator="<=" if domain.group(2) in {"<=", "≤"} else "<",
                comparator_upper="<=" if domain.group(4) in {"<=", "≤"} else "<",
                integral_lower=domain.group(1),
                integral_upper=domain.group(5),
                operation="solve",
            )
    radian_domain = _BOUNDED_RADIAN_DOMAIN.search(cleaned)
    if radian_domain is not None and any(
        name in cleaned.lower() for name in ("sin", "cos", "tan", "sec", "csc", "cot")
    ):
        from app.modules.math import solve as math_solve

        variable = radian_domain.group(3)
        pairs = math_solve.try_extract_equations_from_text(cleaned)
        if len(pairs) == 1:
            lhs, rhs = pairs[0]
        elif "sec" in cleaned.lower() and "undefined" in cleaned.lower():
            lhs, rhs = f"cos({variable})", "0"
        else:
            lhs = rhs = ""
        if lhs and rhs:

            def normalize_bound(value: str) -> str:
                return re.sub(r"(?<=\d)\s*(?=(?:pi|π)\b)", "*", value.replace("π", "pi"))

            return MathIntent(
                kind="trig",
                school_op="bounded_radian_equation",
                lhs=lhs,
                rhs=rhs,
                variable=variable,
                comparator="<=" if radian_domain.group(2) in {"<=", "≤"} else "<",
                comparator_upper=("<=" if radian_domain.group(4) in {"<=", "≤"} else "<"),
                integral_lower=normalize_bound(radian_domain.group(1)),
                integral_upper=normalize_bound(radian_domain.group(5)),
                operation="solve",
            )
    if mtm.has_equation(cleaned):
        return None
    if mtm.calc_op(cleaned) is not None:
        return None
    expression = cleaned.strip().rstrip(".?!")
    for prefix in _TRIG_PREFIXES:
        if expression.lower().startswith(prefix + " "):
            expression = expression[len(prefix) :].lstrip()
            break
    rewritten, count = _DEGREE_TRIG_CALL.subn(
        lambda match: f"{match.group(1).lower()}(({match.group(2)})*pi/180)",
        expression,
    )
    if count >= 2:
        parsed = math_expr_or_none(rewritten)
        if parsed is not None:
            return MathIntent(
                kind="trig",
                school_op="expression",
                expr=parsed,
                operation="solve",
            )
    # The same complete-expression path for exact radian inputs. Degree calls
    # are handled above because their unit must be converted explicitly;
    # ``pi``/``π`` already denotes radians and needs no per-call special case.
    radian_expression = expression.replace("π", "pi")
    trig_call_count = sum(
        len(re.findall(rf"\b{name}\s*\(", radian_expression, re.IGNORECASE)) for name in _TRIG_FUNCS
    )
    if trig_call_count >= 2 and re.search(r"\bpi\b", radian_expression, re.IGNORECASE):
        parsed = math_expr_or_none(radian_expression)
        if parsed is not None:
            return MathIntent(
                kind="trig",
                school_op="expression",
                expr=parsed,
                operation="solve",
            )
    lower = cleaned.lower()
    padded = f" {lower} "
    func = None
    for name in _TRIG_FUNCS:
        if (
            padded.startswith(f" {name}(")
            or padded.startswith(f" {name} ")
            or f" {name}(" in padded
            or f" {name} " in padded
        ):
            func = name
            break
    if func is None:
        return None
    if "identity" in lower or "law of sines" in lower or "law of cosines" in lower:
        # SSS already covers law of cosines; law of sines needs more sides/angles
        # than we parse here — leave identities to the LLM.
        if "law of sines" in lower:
            return None
        if "identity" in lower:
            return None
    idx = lower.find(func)
    prefix = lower[:idx].strip()
    while prefix:
        for cue in _TRIG_PREFIXES:
            if prefix == cue or prefix.startswith(cue + " "):
                prefix = prefix[len(cue) :].strip()
                break
        else:
            break
    if prefix:
        return None
    rest = cleaned[idx + len(func) :].strip().rstrip(".?!")
    # "sin of 30 degrees" / "sine of 30" — English, not sin(30).
    if rest.lower().startswith("of"):
        rest = rest[2:].lstrip()
    if rest.startswith("("):
        depth = 0
        close = None
        for i, char in enumerate(rest):
            depth += (char == "(") - (char == ")")
            if depth == 0:
                close = i
                break
        if close is None:
            return None
        suffix = rest[close + 1 :].strip()
        if suffix and suffix.lower() not in {
            "degrees",
            "degree",
            "deg",
            "radians",
            "radian",
            "rad",
            "°",
        }:
            # Do not certify the first call after dropping +cos(...) etc.
            return None
        rest = (rest[1:close] + " " + suffix).strip()
    angle_unit = None
    for unit in ("degrees", "degree", "deg", "radians", "radian", "rad", "°"):
        if rest.lower().endswith(unit):
            angle_unit = "degrees" if unit in {"degrees", "degree", "deg", "°"} else "radians"
            rest = rest[: -len(unit)].strip()
            break
    arg = math_expr_or_none(rest)
    if arg is None:
        return None
    canon = _TRIG_CANON.get(func, func)
    numeric = mtm._NUM.fullmatch(arg)
    if angle_unit == "degrees" or (angle_unit is None and numeric is not None):
        # Keep the established school shorthand sin 30 = sin(30 degrees).
        return MathIntent(
            kind="trig",
            school_op=canon,
            percent_base=float(arg) if numeric is not None else None,
            expr=f"{canon}(({arg})*pi/180)",
            operation="solve",
        )
    if angle_unit is None and "pi" not in arg and arg != "e":
        return None
    return MathIntent(
        kind="trig",
        school_op=canon,
        expr=f"{canon}({arg})",
        operation="solve",
    )


def _verified_block_trig(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if (
        intent.school_op in {"bounded_degree_equation", "bounded_radian_equation"}
        and intent.lhs
        and intent.rhs
        and intent.integral_lower is not None
        and intent.integral_upper is not None
    ):
        from sympy import (
            Eq,
            FiniteSet,
            Interval,
            Symbol,
            cos,
            latex,
            pi,
            simplify,
            sin,
            solve,
            solveset,
            tan,
        )

        from app.modules.math import solve as math_solve
        from app.modules.math.solve.parse import parse_equation

        _, lhs, rhs = parse_equation(
            EquationInput(lhs=intent.lhs, rhs=intent.rhs, variables=[intent.variable])
        )
        symbols = getattr(lhs, "free_symbols", set()) | getattr(rhs, "free_symbols", set())
        variable = next(
            (symbol for symbol in symbols if str(symbol) == intent.variable),
            Symbol(intent.variable, real=True),
        )
        if intent.school_op == "bounded_degree_equation":
            low = float(intent.integral_lower) * pi / 180
            high = float(intent.integral_upper) * pi / 180
        else:
            low = math_solve._parse_expression(intent.integral_lower, [])
            high = math_solve._parse_expression(intent.integral_upper, [])
        domain = Interval(
            low,
            high,
            left_open=intent.comparator == "<",
            right_open=intent.comparator_upper == "<",
        )
        solved = solveset(Eq(lhs, rhs), variable, domain=domain)
        if not isinstance(solved, FiniteSet):
            return None
        display_values = (
            [simplify(value * 180 / pi) for value in solved]
            if intent.school_op == "bounded_degree_equation"
            else list(solved)
        )
        display_values.sort(key=lambda value: float(value))
        if not display_values:
            answer = r"\text{no solution}"
        else:
            suffix = "^\\circ" if intent.school_op == "bounded_degree_equation" else ""
            joined = r",\;".join(f"{latex(value)}{suffix}" for value in display_values)
            answer = f"{intent.variable} = {joined}"
        degree_suffix = "^\\circ" if intent.school_op == "bounded_degree_equation" else ""
        left_comparator = r"\le" if intent.comparator == "<=" else "<"
        right_comparator = r"\le" if intent.comparator_upper == "<=" else "<"
        domain_tex = (
            f"{latex(low)}{degree_suffix} {left_comparator} {intent.variable} "
            f"{right_comparator} {latex(high)}{degree_suffix}"
        )
        periodic: str | None = None
        if rhs == 0 and getattr(lhs, "func", None) in {sin, cos, tan} and len(lhs.args) == 1:
            integer = Symbol("k", integer=True)
            angle = lhs.args[0]
            if lhs.func == cos:
                angle_solution = pi / 2 + integer * pi
                zero_law = r"\cos(\theta)=0 \Rightarrow \theta=\frac{\pi}{2}+k\pi"
            else:
                angle_solution = integer * pi
                function_name = "sin" if lhs.func == sin else "tan"
                zero_law = rf"\{function_name}(\theta)=0 \Rightarrow \theta=k\pi"
            solved_general = solve(Eq(angle, angle_solution), variable)
            if len(solved_general) == 1:
                general = simplify(solved_general[0])
                k_values: list[str] = []
                for value in display_values:
                    candidates = solve(Eq(general, value), integer)
                    if len(candidates) == 1 and candidates[0].is_integer:
                        rendered = latex(candidates[0])
                        if rendered not in k_values:
                            k_values.append(rendered)
                joined_k = r",\;".join(k_values)
                interval_step = (
                    f"$k = {joined_k}$ gives every value in ${domain_tex}$."
                    if k_values
                    else f"Keep the values of $k$ that place $x$ in ${domain_tex}$."
                )
                periodic = (
                    "**1. Use the periodic zero law**\n\n"
                    f"${zero_law}, \\quad k\\in\\mathbb{{Z}}$\n\n"
                    "**2. Substitute the angle**\n\n"
                    f"${latex(angle)} = {latex(angle_solution)}$\n\n"
                    "**3. Solve for the variable**\n\n"
                    f"${intent.variable} = {latex(general)}$\n\n"
                    "**4. Apply the stated interval**\n\n"
                    f"{interval_step}\n\n"
                )
        direct = (
            f"**Given:** ${latex(lhs)} = {latex(rhs)}$\n\n"
            f"**Domain:** ${domain_tex}$\n\n"
            + (periodic or "**Solve within the stated interval**\n")
            + f"${answer}$\n\n"
            + f"```answer\n{answer}\n```\n"
        )
        lines.extend(
            [
                f"Equation: {latex(lhs)} = {latex(rhs)}",
                f"Domain: {domain_tex}",
                f"Solutions in the domain: {answer}",
            ]
        )
        block = _finish_with_answer(lines, answer)
        return VerifiedMathBlock(
            text=block.text,
            canonical_fence=block.canonical_fence,
            canonical_answer=block.canonical_answer,
            direct_reply=direct,
        )
    if (
        intent.school_op == "sas_area"
        and intent.percent_base is not None
        and intent.percent_rate is not None
        and intent.point_x is not None
    ):
        from app.modules.math import formulas as math_formulas

        answer = math_formulas.sas_triangle_area(
            intent.percent_base, intent.percent_rate, intent.point_x
        )
        lines.append(f"SAS area = {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op and intent.percent_base is not None:
        answer = math_school.evaluate_trig_degrees(intent.school_op, intent.percent_base)
        if "exact" in (intent._request_text or "").lower() and intent.expr:
            from sympy import latex, simplify, together

            from app.modules.math import solve as math_solve

            answer = latex(together(simplify(math_solve._parse_expression(intent.expr, []))))
        lines.append(f"{intent.school_op}({intent.percent_base:g}°) = {answer}")
        block = _finish_with_answer(lines, answer)
        if intent.school_op in {"sin", "cos", "tan"} and float(intent.percent_base).is_integer():
            from app.modules.math.solve.teaching_algebra import standard_degrees, unit_circle_spec

            angle = int(intent.percent_base)
            if standard_degrees(angle) is not None and abs(angle) <= 360:
                circle = unit_circle_spec(angle, answer)
                fields = (
                    {"sin": circle.sine, "cos": circle.cosine, "tan": circle.tangent}
                    if circle
                    else {}
                )
                if circle is not None and fields.get(intent.school_op) == answer:
                    return _attach_picture(block, circle, intent, direct=True)
        if intent.school_op in {"sin", "cos"} and float(intent.percent_base).is_integer():
            from sympy import cos, latex, pi, simplify, sin, together

            angle = int(intent.percent_base)
            standards = (-90, -60, -45, -30, 30, 45, 60, 90)
            pair = next(
                (
                    (first, second)
                    for first in standards
                    for second in standards
                    if first + second == angle
                ),
                None,
            )
            if pair is not None:
                first, second = pair
                trig = cos if intent.school_op == "cos" else sin
                sign = "-" if intent.school_op == "cos" else "+"
                left_first = "cos" if intent.school_op == "cos" else "sin"
                left_second = "cos"
                right_first = "sin" if intent.school_op == "cos" else "cos"
                right_second = "sin"
                complementary = sin if intent.school_op == "cos" else cos
                components = (
                    trig(first * pi / 180),
                    cos(second * pi / 180),
                    complementary(first * pi / 180),
                    sin(second * pi / 180),
                )
                signed_second = (
                    simplify(components[0] * components[1] - components[2] * components[3])
                    if intent.school_op == "cos"
                    else simplify(components[0] * components[1] + components[2] * components[3])
                )
                direct = (
                    "**Split into familiar angles**\n"
                    f"${angle}^\\circ = {first}^\\circ + {second}^\\circ$\n\n"
                    "**Use the angle-sum identity**\n"
                    f"$\\{intent.school_op}({angle}^\\circ) = "
                    f"\\{left_first}({first}^\\circ)\\{left_second}({second}^\\circ) "
                    f"{sign} \\{right_first}({first}^\\circ)\\{right_second}({second}^\\circ)$\n\n"
                    "**Write the exact component values**\n"
                    f"$\\{left_first}({first}^\\circ)={latex(components[0])}$\n\n"
                    f"$\\{left_second}({second}^\\circ)={latex(components[1])}$\n\n"
                    f"$\\{right_first}({first}^\\circ)={latex(components[2])}$\n\n"
                    f"$\\{right_second}({second}^\\circ)={latex(components[3])}$\n\n"
                    "**Substitute and simplify**\n"
                    f"$\\{intent.school_op}({angle}^\\circ) = {latex(signed_second)}$\n\n"
                    f"```answer\n{answer}\n```\n"
                )
                return replace(block, direct_reply=direct)
        return block
    if intent.expr:
        answer = math_school.evaluate_trig_expr(intent.expr)
        lines.append(f"Result: {answer}")
        return _finish_with_answer(lines, answer)
    return None
