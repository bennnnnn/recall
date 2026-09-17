"""Closed-formula extractors on existing MathIntent kinds."""

from __future__ import annotations

import math
import re

from app.models.schemas.math import MathIntent
from app.services.math import match as mtm
from app.services.math.tools.helpers import math_expr_or_none
from app.services.text_match import word_index


def _finite_match_value(match: re.Match[str]) -> float | None:
    try:
        value = float(match.group(0))
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def _number_immediately_before(text: str, idx: int) -> re.Match[str] | None:
    end = idx
    while end > 0 and text[end - 1].isspace():
        end -= 1
    found = None
    for match in mtm._NUM.finditer(text[:end]):
        found = match
    if found is None or found.end() != end:
        return None
    return found


def _exactly_n_numbers(cleaned: str, count: int) -> list[float] | None:
    matches = list(mtm._NUM.finditer(cleaned))
    if len(matches) != count:
        return None
    values: list[float] = []
    for match in matches:
        value = _finite_match_value(match)
        if value is None:
            return None
        values.append(value)
    return values


def _extract_discount(cleaned: str, lower: str) -> MathIntent | None:
    if "% of " in lower:
        return None
    if cleaned.count("%") != 1:
        return None
    if word_index(lower, "discount") == -1 and word_index(lower, "off") == -1:
        return None
    nums = list(mtm._NUM.finditer(cleaned))
    if len(nums) != 2:
        return None
    pct_at = cleaned.find("%")
    rate_m = _number_immediately_before(cleaned, pct_at)
    if rate_m is None:
        return None
    base_m = nums[0] if nums[0].span() != rate_m.span() else nums[1]
    if base_m.span() == rate_m.span():
        return None
    rate = _finite_match_value(rate_m)
    base = _finite_match_value(base_m)
    if rate is None or base is None:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="discount",
        percent_rate=rate,
        percent_base=base,
        operation="solve",
    )


def _extract_with_percent_total(cleaned: str, lower: str) -> MathIntent | None:
    if "% of " in lower or cleaned.count("%") != 1:
        return None
    if word_index(lower, "with") == -1 and word_index(lower, "plus") == -1:
        return None
    if word_index(lower, "tax") == -1 and word_index(lower, "tip") == -1:
        return None
    nums = list(mtm._NUM.finditer(cleaned))
    if len(nums) != 2:
        return None
    pct_at = cleaned.find("%")
    rate_m = _number_immediately_before(cleaned, pct_at)
    if rate_m is None:
        return None
    base_m = nums[0] if nums[0].span() != rate_m.span() else nums[1]
    if base_m.span() == rate_m.span():
        return None
    rate = _finite_match_value(rate_m)
    base = _finite_match_value(base_m)
    if rate is None or base is None:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="percent_increase",
        percent_rate=rate,
        percent_base=base,
        operation="solve",
    )


def _extract_percent_change_from(cleaned: str, lower: str) -> MathIntent | None:
    if "%" in cleaned:
        return None
    if "percent change from" not in lower and "percentage change from" not in lower:
        return None
    values = _exactly_n_numbers(cleaned, 2)
    if values is None:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="percent_change_from",
        percent_base=values[0],
        percent_rate=values[1],
        operation="solve",
    )


def _extract_proportion(cleaned: str, lower: str) -> MathIntent | None:
    values = _exactly_n_numbers(cleaned, 3)
    if values is None:
        return None
    inverse = word_index(lower, "inverse") != -1
    direct = (
        word_index(lower, "cost") != -1
        or word_index(lower, "costs") != -1
        or "direct proportion" in lower
    )
    if inverse and ("proportion" in lower or word_index(lower, "inversely") != -1):
        return MathIntent(
            kind="arithmetic",
            school_op="inverse_proportion",
            stats_numbers=values,
            operation="solve",
        )
    if inverse or not direct:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="direct_proportion",
        stats_numbers=values,
        operation="solve",
    )


def _extract_rounding(cleaned: str, lower: str) -> MathIntent | None:
    if word_index(lower, "round") == -1:
        return None
    values = _exactly_n_numbers(cleaned, 2)
    if values is None:
        return None
    places = values[1]
    if not places.is_integer() or places < 0:
        return None
    if "decimal" in lower:
        op = "round_decimal"
    elif "significant" in lower:
        op = "round_sigfigs"
        if places < 1:
            return None
    else:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op=op,
        percent_base=values[0],
        combo_n=int(places),
        operation="solve",
    )


def _extract_present_value(cleaned: str, lower: str) -> MathIntent | None:
    if "present value" not in lower:
        return None
    if cleaned.count("%") != 1 or "year" not in lower:
        return None
    if any(word_index(lower, word) != -1 for word in ("month", "weekly", "daily", "continuous")):
        return None
    nums = list(mtm._NUM.finditer(cleaned))
    if len(nums) != 3:
        return None
    pct_at = cleaned.find("%")
    year_at = lower.find("year")
    rate_m = _number_immediately_before(cleaned, pct_at)
    years_m = _number_immediately_before(cleaned, year_at)
    if rate_m is None or years_m is None:
        return None
    amount_m = None
    for match in nums:
        if match.span() not in {rate_m.span(), years_m.span()}:
            amount_m = match
            break
    if amount_m is None:
        return None
    rate = _finite_match_value(rate_m)
    years_value = _finite_match_value(years_m)
    amount = _finite_match_value(amount_m)
    if rate is None or years_value is None or amount is None or not years_value.is_integer():
        return None
    years = int(years_value)
    if years < 1 or years > 100:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="present_value",
        percent_base=amount,
        percent_rate=rate,
        combo_n=years,
        operation="solve",
    )


def extract_arithmetic_formulas(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    for extractor in (
        _extract_discount,
        _extract_with_percent_total,
        _extract_percent_change_from,
        _extract_present_value,
        _extract_proportion,
        _extract_rounding,
    ):
        intent = extractor(cleaned, lower)
        if intent is not None:
            return intent
    return None


def extract_infinite_geometric(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "infinity" not in lower and "infinite" not in lower:
        return None
    if "sum" not in lower and "series" not in lower:
        return None
    from app.services.math.formulas import is_convergent_geometric
    from app.services.math.match.discrete import numeric_data_values

    idx = lower.rfind(" of ")
    if idx == -1:
        return None
    terms = numeric_data_values(cleaned[idx + 4 :])
    if terms is None or len(terms) < 3:
        return None
    if len(list(mtm._NUM.finditer(cleaned))) != len(terms):
        return None
    if not is_convergent_geometric(terms):
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="infinite_gp",
        stats_numbers=terms,
        operation="solve",
    )


def _linear_abc(cleaned: str) -> tuple[float, float, float] | None:
    from sympy import Symbol, diff

    from app.services.math.solve import try_extract_equation_from_text
    from app.services.math.solve.parse import _parse_expression

    extracted = try_extract_equation_from_text(cleaned)
    if extracted is None:
        return None
    parsed = _parse_expression(f"({extracted.lhs})-({extracted.rhs})", ["x", "y"])
    x, y = Symbol("x"), Symbol("y")
    if parsed.free_symbols - {x, y}:
        return None
    if diff(parsed, x, 2) != 0 or diff(parsed, y, 2) != 0 or diff(parsed, x, y) != 0:
        return None
    a = float(parsed.coeff(x))
    b = float(parsed.coeff(y))
    c = float(parsed.subs({x: 0, y: 0}))
    if a == 0 and b == 0:
        return None
    return a, b, c


def extract_coord_formulas(cleaned: str) -> MathIntent | None:
    from app.services.math.match.coordinate_vector import literal_math_tuples

    lower = cleaned.lower()
    points = literal_math_tuples(cleaned, "(", ")")
    if word_index(lower, "slope") != -1 or word_index(lower, "midpoint") != -1:
        return None
    if points is not None and len(points) == 2 and all(len(pt) == 2 for pt in points):
        if word_index(lower, "distance") != -1:
            return None
        if "line" not in lower and "equation" not in lower:
            return None
        (x1, y1), (x2, y2) = (points[0][0], points[0][1]), (points[1][0], points[1][1])
        return MathIntent(
            kind="coord",
            school_op="line",
            point_x=x1,
            point_y=y1,
            x2=x2,
            y2=y2,
            operation="solve",
        )
    if word_index(lower, "distance") == -1:
        return None
    if points is None or len(points) != 1 or len(points[0]) != 2:
        return None
    coeffs = _linear_abc(cleaned)
    if coeffs is None:
        return None
    return MathIntent(
        kind="coord",
        school_op="point_to_line",
        point_x=points[0][0],
        point_y=points[0][1],
        vec_a=[coeffs[0], coeffs[1], coeffs[2]],
        operation="solve",
    )


def extract_vector_formulas(cleaned: str) -> MathIntent | None:
    from app.services.math.match.coordinate_vector import literal_math_tuples

    lower = cleaned.lower()
    vecs = literal_math_tuples(cleaned, "<", ">") or []
    if not vecs:
        return None
    if "unit vector" in lower:
        if len(vecs) != 1:
            return None
        return MathIntent(kind="vector", school_op="unit", vec_a=vecs[0], operation="solve")
    if word_index(lower, "projection") != -1 or word_index(lower, "proj") != -1:
        if len(vecs) != 2 or len(vecs[0]) != len(vecs[1]):
            return None
        return MathIntent(
            kind="vector",
            school_op="projection",
            vec_a=vecs[0],
            vec_b=vecs[1],
            operation="solve",
        )
    if word_index(lower, "angle") != -1:
        if len(vecs) != 2 or len(vecs[0]) != len(vecs[1]):
            return None
        return MathIntent(
            kind="vector",
            school_op="angle",
            vec_a=vecs[0],
            vec_b=vecs[1],
            operation="solve",
        )
    return None


def extract_sas_area(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "area" not in lower or "triangle" not in lower:
        return None
    if "angle" not in lower:
        return None
    if word_index(lower, "sides") == -1 and "included" not in lower:
        return None
    values = _exactly_n_numbers(cleaned, 3)
    if values is None:
        return None
    angle = None
    for cue in ("angle", "included"):
        idx = word_index(lower, cue)
        if idx == -1:
            continue
        after = mtm._NUM.search(cleaned, idx)
        if after is not None:
            angle = _finite_match_value(after)
            break
    if angle is None:
        return None
    sides = [value for value in values if value != angle]
    if len(sides) != 2:
        return None
    return MathIntent(
        kind="trig",
        school_op="sas_area",
        percent_base=sides[0],
        percent_rate=sides[1],
        point_x=angle,
        operation="solve",
    )


def extract_probability_formulas(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    compact = lower.replace(" ", "")
    if "geometric" in lower:
        k_at = compact.find("k=")
        p_at = compact.find("p=")
        if k_at == -1 or p_at == -1 or "n=" in compact:
            return MathIntent(kind="probability", school_op="geometric", operation="solve")
        values = _exactly_n_numbers(cleaned, 2)
        if values is None:
            return MathIntent(kind="probability", school_op="geometric", operation="solve")
        k = values[0] if k_at < p_at else values[1]
        p = values[1] if k_at < p_at else values[0]
        if not k.is_integer():
            return MathIntent(kind="probability", school_op="geometric", operation="solve")
        return MathIntent(
            kind="probability",
            school_op="geometric",
            combo_k=int(k),
            percent_base=p,
            operation="solve",
        )
    if "poisson" in lower:
        k_at = compact.find("k=")
        lam_at = compact.find("lambda=")
        if lam_at == -1:
            lam_at = compact.find("λ=")
        if k_at == -1 or lam_at == -1:
            return MathIntent(kind="probability", school_op="poisson", operation="solve")
        values = _exactly_n_numbers(cleaned, 2)
        if values is None:
            return MathIntent(kind="probability", school_op="poisson", operation="solve")
        k = values[0] if k_at < lam_at else values[1]
        lam = values[1] if k_at < lam_at else values[0]
        if not k.is_integer():
            return MathIntent(kind="probability", school_op="poisson", operation="solve")
        return MathIntent(
            kind="probability",
            school_op="poisson",
            combo_k=int(k),
            percent_base=lam,
            operation="solve",
        )
    if word_index(lower, "bayes") != -1 or "p(a|b)" in compact:
        values = _exactly_n_numbers(cleaned, 3)
        if values is None:
            return MathIntent(kind="probability", school_op="bayes", operation="solve")
        return MathIntent(
            kind="probability",
            school_op="bayes",
            vec_a=values,
            operation="solve",
        )
    if word_index(lower, "complement") != -1:
        values = _exactly_n_numbers(cleaned, 1)
        if values is None:
            return MathIntent(kind="probability", school_op="complement", operation="solve")
        return MathIntent(
            kind="probability",
            school_op="complement",
            percent_base=values[0],
            operation="solve",
        )
    return None


def _complex_op(lower: str) -> str | None:
    if word_index(lower, "modulus") != -1 or word_index(lower, "magnitude") != -1:
        return "modulus"
    if word_index(lower, "argument") != -1 or word_index(lower, "arg") != -1:
        return "argument"
    if word_index(lower, "conjugate") != -1:
        return "conjugate"
    if "polar" in lower:
        return "polar"
    return None


def extract_complex_op(cleaned: str) -> str | None:
    return _complex_op(cleaned.lower())


def _named_axis_bounds(text: str, var: str) -> tuple[str, str] | None:
    lower = text.lower()
    needle = f"{var}="
    idx = lower.find(needle)
    if idx == -1:
        needle = f"{var} ="
        idx = lower.find(needle)
        if idx == -1:
            return None
    rest = text[idx + len(needle) :]
    to_at = rest.lower().find(" to ")
    if to_at == -1:
        return None
    lo = rest[:to_at].strip().rstrip(",")
    hi_part = rest[to_at + 4 :].strip()
    end = 0
    while end < len(hi_part) and not hi_part[end].isspace() and hi_part[end] not in ",;":
        end += 1
    hi = hi_part[:end].strip()
    if not lo or not hi:
        return None
    return lo, hi


def _integral_expr_after(cleaned: str, cue: str) -> str | None:
    lower = cleaned.lower()
    start = lower.find(cue)
    if start == -1:
        return None
    rest = cleaned[start + len(cue) :].lstrip()
    if rest.lower().startswith("of "):
        rest = rest[3:]
    from_at = rest.lower().find(" from ")
    if from_at == -1:
        return None
    return math_expr_or_none(rest[:from_at].strip())


def extract_triple_integral_intent(cleaned: str) -> MathIntent | None:
    x_bounds = _named_axis_bounds(cleaned, "x")
    y_bounds = _named_axis_bounds(cleaned, "y")
    z_bounds = _named_axis_bounds(cleaned, "z")
    if x_bounds is None or y_bounds is None or z_bounds is None:
        return None
    if "triple" not in cleaned.lower() and "integral" not in cleaned.lower():
        return None
    expr = _integral_expr_after(cleaned, "triple integral") or _integral_expr_after(
        cleaned, "integral"
    )
    if expr is None:
        return None
    return MathIntent(
        kind="calculus",
        operation="integrate",
        school_op="triple_integral",
        expr=expr,
        variable="x",
        variable2="y",
        variable3="z",
        integral_lower=x_bounds[0],
        integral_upper=x_bounds[1],
        integral_lower2=y_bounds[0],
        integral_upper2=y_bounds[1],
        integral_lower3=z_bounds[0],
        integral_upper3=z_bounds[1],
    )


def extract_average_value_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "average value" not in lower:
        return None
    of_at = lower.find(" of ")
    from_at = lower.find(" from ")
    to_at = lower.find(" to ", from_at + 1) if from_at != -1 else -1
    if of_at == -1 or from_at == -1 or to_at == -1:
        return None
    expr = math_expr_or_none(cleaned[of_at + 4 : from_at].strip())
    lo = cleaned[from_at + 6 : to_at].strip()
    hi_part = cleaned[to_at + 4 :].strip()
    end = 0
    while end < len(hi_part) and not hi_part[end].isspace() and hi_part[end] not in ",;":
        end += 1
    hi = hi_part[:end].strip()
    if expr is None or not lo or not hi:
        return None
    return MathIntent(
        kind="calculus",
        operation="integrate",
        school_op="average_value",
        expr=expr,
        variable="x",
        integral_lower=lo,
        integral_upper=hi,
    )


def extract_linear_approx_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "linear approximation" not in lower and "linearize" not in lower:
        return None
    of_at = lower.find(" of ")
    at_at = lower.find(" at ")
    if of_at == -1 or at_at == -1 or at_at < of_at:
        return None
    expr = math_expr_or_none(cleaned[of_at + 4 : at_at].strip())
    point_m = mtm._NUM.search(cleaned, at_at)
    if expr is None or point_m is None:
        return None
    if mtm._NUM.search(cleaned, point_m.end()) is not None:
        return None
    return MathIntent(
        kind="calculus",
        operation="simplify",
        school_op="linear_approx",
        expr=expr,
        variable="x",
        limit_point=point_m.group(0),
    )


def extract_gradient_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if word_index(lower, "gradient") == -1 and word_index(lower, "grad") == -1:
        return None
    of_at = lower.find(" of ")
    if of_at == -1:
        return None
    expr = math_expr_or_none(cleaned[of_at + 4 :].strip())
    if expr is None:
        return None
    return MathIntent(
        kind="calculus",
        operation="partial",
        school_op="gradient",
        expr=expr,
        variable="x",
    )


def extract_directional_intent(cleaned: str) -> MathIntent | None:
    from app.services.math.match.coordinate_vector import literal_math_tuples

    lower = cleaned.lower()
    if "directional derivative" not in lower:
        return None
    of_at = lower.find(" of ")
    at_at = lower.find(" at ")
    if of_at == -1 or at_at == -1:
        return None
    expr = math_expr_or_none(cleaned[of_at + 4 : at_at].strip())
    points = literal_math_tuples(cleaned, "(", ")")
    vecs = literal_math_tuples(cleaned, "<", ">") or []
    if expr is None or points is None or len(points) != 1 or len(vecs) != 1:
        return None
    if len(points[0]) != len(vecs[0]):
        return None
    return MathIntent(
        kind="calculus",
        operation="partial",
        school_op="directional",
        expr=expr,
        vec_a=list(points[0]),
        vec_b=vecs[0],
        variable="x",
    )


def extract_div_curl_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    op = None
    if word_index(lower, "divergence") != -1 or word_index(lower, "div") != -1:
        op = "divergence"
    elif word_index(lower, "curl") != -1:
        op = "curl"
    if op is None:
        return None
    start = cleaned.find("<")
    end = cleaned.find(">", start + 1) if start != -1 else -1
    if start == -1 or end == -1:
        return None
    expr = cleaned[start + 1 : end].strip()
    if math_expr_or_none(expr.replace(",", "+")) is None:
        return None
    return MathIntent(
        kind="calculus",
        operation="partial",
        school_op=op,
        expr=expr,
        variable="x",
    )


def extract_implicit_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "implicit" not in lower:
        return None
    if "differentiate" not in lower and "derivative" not in lower and "dy/dx" not in lower:
        return None
    eq = cleaned.find("=")
    if eq <= 0:
        return None
    raw_lhs = cleaned[:eq]
    for cue in ("implicitly differentiate", "implicit differentiate", "implicit derivative of"):
        idx = lower.find(cue)
        if idx != -1:
            raw_lhs = cleaned[idx + len(cue) : eq]
            break
    lhs = math_expr_or_none(raw_lhs.strip())
    rhs = math_expr_or_none(cleaned[eq + 1 :].strip())
    if not lhs or not rhs:
        return None
    return MathIntent(
        kind="calculus",
        operation="differentiate",
        school_op="implicit",
        lhs=lhs,
        rhs=rhs,
        expr=f"({lhs})-({rhs})",
        variable="x",
    )


FORMULA_CALCULUS_EXTRACTORS = (
    extract_implicit_intent,
    extract_triple_integral_intent,
    extract_average_value_intent,
    extract_linear_approx_intent,
    extract_gradient_intent,
    extract_directional_intent,
    extract_div_curl_intent,
)
