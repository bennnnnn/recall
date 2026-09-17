"""Extractors + verified blocks for remaining school kinds."""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Callable
from fractions import Fraction
from typing import Any

from app.core.config import Settings
from app.models.schemas.math import MathIntent
from app.services.math import match as mtm
from app.services.math import school as math_school
from app.services.math.match.coordinate_vector import literal_math_tuples
from app.services.math.match.scan import _NUM
from app.services.math.tools.block import VerifiedMathBlock, _finish_with_answer
from app.services.math.tools.block.common import format_quantity
from app.services.math.tools.helpers import math_expr_or_none, substituted_eval_expr
from app.services.text_match import word_index

logger = logging.getLogger(__name__)

_TRIG_FUNCS = ("sine", "cosine", "tangent", "sin", "cos", "tan")
_TRIG_CANON = {"sine": "sin", "cosine": "cos", "tangent": "tan"}
_TRIG_PREFIXES = (
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
_PROB_NUMBER = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
_BINOMIAL_PARAM = re.compile(
    rf"\b([nkp])\s*=\s*({_PROB_NUMBER}(?:\s*/\s*{_PROB_NUMBER})?)(?=\s|[,;.!?]|$)",
    re.IGNORECASE,
)
_SEQUENCE_LIST_MAX = 20
_SEQUENCE_N_MAX = 10_000
_INTEREST_YEAR_MAX = 100
_PERCENT_INCREASE_WORDS = ("increase", "increased", "increasing", "markup", "marked up")
_PERCENT_DECREASE_WORDS = ("decrease", "decreased", "decreasing")
_RATIO_SPLIT_WORDS = ("split", "share", "divide")
_ORDINAL_SUFFIXES = ("st", "nd", "rd", "th")


def _extract_unit_intent(cleaned: str) -> MathIntent | None:
    from app.services.math.match.units import QUANTITY_NUMBER

    lower = cleaned.lower()
    if "convert" not in lower and " to " not in lower:
        return None
    if "convert" not in lower:
        return None
    after = QUANTITY_NUMBER.search(cleaned)
    if after is None:
        return None
    value = float(after.group(0))
    # Temperature conversions allow zero and negative quantities. Retain
    # the sign instead of skipping to a later positive number.
    if abs(value) == float("inf"):
        return None
    idx = lower.find(" to ")
    if idx == -1:
        return None
    destination = cleaned[idx + 4 :].strip().split()
    if not destination or (len(destination) > 1 and destination[1:] != ["please"]):
        return None
    dest = destination[0].strip("?.")
    # The complete source/destination must be one conversion. Dropping a
    # second request could otherwise turn it into a partial direct answer.
    source = cleaned[after.end() : idx].strip().split()
    if len(source) != 1:
        return None
    src = source[0]
    if src.lower() in {"to"}:
        return None
    if not src or not dest:
        return None
    return MathIntent(
        kind="unit",
        school_op="convert",
        percent_base=value,
        unit_from=src,
        unit_to=dest,
        operation="solve",
    )


def _extract_coord_intent(cleaned: str) -> MathIntent | None:
    from app.services.math.tools.extractors.formulas import extract_coord_formulas

    extra = extract_coord_formulas(cleaned)
    if extra is not None:
        return extra
    lower = cleaned.lower()
    op: str | None = None
    if "distance" in lower or "how far" in lower:
        op = "distance"
    elif "midpoint" in lower:
        op = "midpoint"
    elif "slope" in lower:
        op = "slope"
    if op is None:
        return None
    # Literal pairs use Euclidean geometry; spherical/geodesic requests
    # require domain information that these operands do not contain.
    if op == "distance" and re.search(r"\b(?:sphere|spherical|geodesic)\b", lower):
        return None
    pts = _two_points(cleaned)
    if pts is None:
        return None
    (x1, y1), (x2, y2) = pts
    return MathIntent(
        kind="coord",
        school_op=op,
        point_x=x1,
        point_y=y1,
        x2=x2,
        y2=y2,
        operation="solve",
    )


def _two_points(text: str) -> tuple[tuple[float, float], tuple[float, float]] | None:
    found = literal_math_tuples(text, "(", ")")
    if found is None or len(found) != 2 or any(len(point) != 2 for point in found):
        return None
    return (found[0][0], found[0][1]), (found[1][0], found[1][1])


def _extract_vector_intent(cleaned: str) -> MathIntent | None:
    from app.services.math.tools.extractors.formulas import extract_vector_formulas

    extra = extract_vector_formulas(cleaned)
    if extra is not None:
        return extra
    lower = cleaned.lower()
    op: str | None = None
    if "cross" in lower:
        op = "cross"
    elif "dot" in lower:
        op = "dot"
    elif "magnitude" in lower or "norm of" in lower:
        op = "magnitude"
    if op is None:
        return None
    vecs = _angle_vectors(cleaned)
    if not vecs:
        return None
    if op == "magnitude":
        if len(vecs) != 1:
            return None
        return MathIntent(kind="vector", school_op=op, vec_a=vecs[0], operation="solve")
    if len(vecs) != 2 or len(vecs[0]) != len(vecs[1]):
        return None
    return MathIntent(kind="vector", school_op=op, vec_a=vecs[0], vec_b=vecs[1], operation="solve")


def _angle_vectors(text: str) -> list[list[float]]:
    return literal_math_tuples(text, "<", ">") or []


def _extract_trig_intent(cleaned: str) -> MathIntent | None:
    from app.services.math.tools.extractors.formulas import extract_sas_area

    sas = extract_sas_area(cleaned)
    if sas is not None:
        return sas
    if mtm.has_equation(cleaned):
        return None
    if mtm.calc_op(cleaned) is not None:
        return None
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


def _count_char(text: str, needle: str) -> int:
    count = 0
    for char in text:
        if char == needle:
            count += 1
    return count


def _has_any_word(lower: str, words: tuple[str, ...]) -> bool:
    return any(word_index(lower, word) != -1 for word in words)


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


def _colon_ratio_parts(text: str) -> tuple[list[float], list[tuple[int, int]]] | None:
    """First ``a:b`` / ``a:b:c`` group. Linear scan, no nested regex."""
    search_from = 0
    length = len(text)
    while search_from < length:
        match = mtm._NUM.search(text, search_from)
        if match is None:
            return None
        cursor = match.end()
        while cursor < length and text[cursor].isspace():
            cursor += 1
        if cursor >= length or text[cursor] != ":":
            search_from = match.end()
            continue
        values = [_finite_match_value(match)]
        spans = [(match.start(), match.end())]
        if values[0] is None:
            search_from = match.end()
            continue
        cursor += 1
        while True:
            while cursor < length and text[cursor].isspace():
                cursor += 1
            nxt = mtm._NUM.match(text, cursor)
            if nxt is None:
                break
            parsed = _finite_match_value(nxt)
            if parsed is None:
                break
            values.append(parsed)
            spans.append((nxt.start(), nxt.end()))
            cursor = nxt.end()
            while cursor < length and text[cursor].isspace():
                cursor += 1
            if cursor < length and text[cursor] == ":":
                cursor += 1
                continue
            break
        finite_parts = [part for part in values if part is not None]
        if len(finite_parts) >= 2:
            return finite_parts, spans
        search_from = match.end()
    return None


def _extract_percent_of(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    pct = lower.find("% of ")
    if pct == -1:
        return None
    rate_m = None
    for match in mtm._NUM.finditer(cleaned[:pct]):
        rate_m = match
    base_m = mtm._NUM.search(cleaned, pct + 5)
    if rate_m is None or base_m is None:
        return None
    rate = _finite_match_value(rate_m)
    base = _finite_match_value(base_m)
    if rate is None or base is None:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="percent",
        percent_rate=rate,
        percent_base=base,
        operation="solve",
    )


def _extract_percent_change(cleaned: str, lower: str) -> MathIntent | None:
    increase = _has_any_word(lower, _PERCENT_INCREASE_WORDS)
    decrease = _has_any_word(lower, _PERCENT_DECREASE_WORDS)
    if increase == decrease:
        return None
    if _count_char(cleaned, "%") != 1:
        return None
    by_at = word_index(lower, "by")
    if by_at == -1:
        return None
    nums = list(mtm._NUM.finditer(cleaned))
    if len(nums) != 2:
        return None
    pct_at = cleaned.find("%")
    rate_m = _number_immediately_before(cleaned, pct_at)
    if rate_m is None:
        return None
    base_m = nums[0] if nums[0].span() != rate_m.span() else nums[1]
    if base_m.span() == rate_m.span() or base_m.end() > by_at or rate_m.start() < by_at:
        return None
    rate = _finite_match_value(rate_m)
    base = _finite_match_value(base_m)
    if rate is None or base is None:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="percent_increase" if increase else "percent_decrease",
        percent_rate=rate,
        percent_base=base,
        operation="solve",
    )


def _extract_percent_is(cleaned: str, lower: str) -> MathIntent | None:
    if _count_char(cleaned, "%") != 0:
        return None
    nums = list(mtm._NUM.finditer(cleaned))
    if len(nums) != 2:
        return None
    part_m: re.Match[str] | None = None
    whole_m: re.Match[str] | None = None
    for cue in (" is what percent of ", " is what percentage of "):
        idx = lower.find(cue)
        if idx == -1:
            continue
        before = None
        for match in nums:
            if match.end() <= idx:
                before = match
        after = mtm._NUM.search(cleaned, idx + len(cue))
        if before is None or after is None:
            return None
        part_m, whole_m = before, after
        break
    if part_m is None or whole_m is None:
        for cue in ("what percent of ", "what percentage of "):
            idx = lower.find(cue)
            if idx == -1:
                continue
            whole = mtm._NUM.search(cleaned, idx + len(cue))
            if whole is None:
                return None
            rest = cleaned[whole.end() :].lstrip()
            if not rest.lower().startswith("is"):
                return None
            after_is = rest[2:]
            if after_is[:1].isalpha():
                return None
            part = mtm._NUM.search(after_is)
            if part is None:
                return None
            part_m, whole_m = part, whole
            break
    if part_m is None or whole_m is None:
        return None
    if {part_m.group(0), whole_m.group(0)} != {nums[0].group(0), nums[1].group(0)}:
        return None
    part_value = _finite_match_value(part_m)
    whole_value = _finite_match_value(whole_m)
    if part_value is None or whole_value is None:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="percent_is",
        percent_rate=part_value,
        percent_base=whole_value,
        operation="solve",
    )


def _extract_ratio_split(cleaned: str, lower: str) -> MathIntent | None:
    if not _has_any_word(lower, _RATIO_SPLIT_WORDS) or "ratio" not in lower:
        return None
    grouped = _colon_ratio_parts(cleaned)
    if grouped is None:
        return None
    parts, spans = grouped
    if any(part < 0 for part in parts) or sum(parts) <= 0:
        return None
    leftover: list[re.Match[str]] = []
    used = set(spans)
    for match in mtm._NUM.finditer(cleaned):
        if (match.start(), match.end()) in used:
            continue
        leftover.append(match)
    if len(leftover) != 1:
        return None
    total = _finite_match_value(leftover[0])
    if total is None or total <= 0:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="ratio_split",
        percent_base=total,
        stats_numbers=parts,
        operation="solve",
    )


def _extract_percent_or_ratio(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    # "% of " stays first so "Out of 250 people, what is 30% of 80?" is 24.
    percent_of = _extract_percent_of(cleaned)
    if percent_of is not None:
        return percent_of
    changed = _extract_percent_change(cleaned, lower)
    if changed is not None:
        return changed
    percent_is = _extract_percent_is(cleaned, lower)
    if percent_is is not None:
        return percent_is
    split = _extract_ratio_split(cleaned, lower)
    if split is not None:
        return split
    if ":" in cleaned and ("ratio" in lower or "simplify" in lower):
        first = mtm._NUM.search(cleaned)
        if first:
            second = mtm._NUM.search(cleaned, first.end())
            if second:
                left = _finite_match_value(first)
                right = _finite_match_value(second)
                if left is None or right is None:
                    return None
                extra = mtm._NUM.search(cleaned, second.end())
                if extra is not None:
                    return None
                return MathIntent(
                    kind="arithmetic",
                    school_op="ratio",
                    percent_rate=left,
                    percent_base=right,
                    operation="solve",
                )
    return None


def _read_leading_int(text: str) -> tuple[int, int] | None:
    i = 0
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i >= n or not text[i].isdigit():
        return None
    j = i
    while j < n and text[j].isdigit():
        j += 1
    if j < n and text[j] in ".":
        return None
    value = int(text[i:j])
    return value, j


def _ordinal_term_n(lower: str) -> int | None:
    i = 0
    n = len(lower)
    found: int | None = None
    while i < n:
        if lower[i].isdigit():
            if i > 0 and lower[i - 1] == ".":
                i += 1
                continue
            j = i
            while j < n and lower[j].isdigit():
                j += 1
            suffix = lower[j : j + 2]
            if suffix in _ORDINAL_SUFFIXES:
                k = j + 2
                while k < n and lower[k].isspace():
                    k += 1
                if lower.startswith("term", k):
                    value = int(lower[i:j])
                    if found is not None:
                        return None
                    found = value
            i = j
        else:
            i += 1
    return found


def _sequence_sum_n(lower: str) -> int | None:
    for cue in ("sum of the first", "sum of first"):
        idx = lower.find(cue)
        if idx == -1:
            continue
        parsed = _read_leading_int(lower[idx + len(cue) :])
        if parsed is None:
            return None
        return parsed[0]
    return None


def _named_even_odd_terms(lower: str) -> list[float] | None:
    has_even = word_index(lower, "even") != -1
    has_odd = word_index(lower, "odd") != -1
    if has_even == has_odd:
        return None
    if "number" not in lower:
        return None
    if has_even:
        return [2.0, 4.0]
    return [1.0, 3.0]


def _listed_sequence_terms(cleaned: str, lower: str) -> list[float] | None:
    idx = lower.rfind(" of ")
    if idx == -1:
        return None
    from app.services.math.match.discrete import numeric_data_values

    numbers = numeric_data_values(cleaned[idx + 4 :])
    if numbers is None or len(numbers) < 3 or len(numbers) > _SEQUENCE_LIST_MAX:
        return None
    return numbers


def _extract_sequence_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    sum_n = _sequence_sum_n(lower)
    term_n = _ordinal_term_n(lower)
    if sum_n is not None:
        if term_n is not None and term_n != sum_n:
            return None
        n = sum_n
        op = "sequence_sum"
    elif term_n is not None:
        n = term_n
        op = "sequence_nth"
    else:
        return None
    if n < 1 or n > _SEQUENCE_N_MAX:
        return None
    named = _named_even_odd_terms(lower) if sum_n is not None else None
    listed = None if named is not None else _listed_sequence_terms(cleaned, lower)
    terms = named if named is not None else listed
    if terms is None:
        return None
    if not math_school.is_ap_or_gp(terms):
        return None
    expected = 1 if named is not None else 1 + len(terms)
    if len(list(mtm._NUM.finditer(cleaned))) != expected:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op=op,
        stats_numbers=terms,
        combo_n=n,
        operation="solve",
    )


def _extract_interest_intent(cleaned: str, lower: str) -> MathIntent | None:
    compound = word_index(lower, "compound") != -1
    simple = word_index(lower, "simple") != -1
    if compound == simple:
        return None
    if simple and "interest" not in lower:
        return None
    if compound and "interest" not in lower and "amount" not in lower:
        return None
    if _count_char(cleaned, "%") != 1:
        return None
    if any(
        word_index(lower, word) != -1
        for word in ("month", "months", "weekly", "daily", "continuous")
    ):
        return None
    nums = list(mtm._NUM.finditer(cleaned))
    if len(nums) != 3:
        return None
    on_at = word_index(lower, "on")
    if on_at == -1:
        on_at = word_index(lower, "of")
    year_at = lower.find("year")
    pct_at = cleaned.find("%")
    if on_at == -1 or year_at == -1 or pct_at == -1:
        return None
    principal_m = mtm._NUM.search(cleaned, on_at + 2)
    rate_m = _number_immediately_before(cleaned, pct_at)
    years_m = _number_immediately_before(cleaned, year_at)
    if principal_m is None or rate_m is None or years_m is None:
        return None
    if {principal_m.span(), rate_m.span(), years_m.span()} != {match.span() for match in nums}:
        return None
    principal = _finite_match_value(principal_m)
    rate = _finite_match_value(rate_m)
    years_value = _finite_match_value(years_m)
    if principal is None or rate is None or years_value is None:
        return None
    if principal <= 0 or rate < 0 or not years_value.is_integer():
        return None
    years = int(years_value)
    if years < 1 or years > _INTEREST_YEAR_MAX:
        return None
    if simple:
        op = "simple_interest"
    elif word_index(lower, "amount") != -1 and "interest" not in lower:
        op = "compound_amount"
    else:
        op = "compound_interest"
    return MathIntent(
        kind="arithmetic",
        school_op=op,
        percent_base=principal,
        percent_rate=rate,
        combo_n=years,
        operation="solve",
    )


def _parse_brace_set(text: str, start: int) -> tuple[list[float], int] | None:
    if start >= len(text) or text[start] != "{":
        return None
    close = text.find("}", start + 1)
    if close == -1:
        return None
    inner = text[start + 1 : close]
    if "{" in inner:
        return None
    values: list[float] = []
    last = 0
    for match in mtm._NUM.finditer(inner):
        gap = inner[last : match.start()].strip()
        if gap not in {"", ","}:
            return None
        parsed = _finite_match_value(match)
        if parsed is None:
            return None
        values.append(parsed)
        last = match.end()
    if not values or inner[last:].strip() not in {"", ","}:
        return None
    return values, close + 1


def _brace_sets(text: str) -> list[list[float]] | None:
    found: list[list[float]] = []
    spans: list[tuple[int, int]] = []
    i = 0
    while i < len(text):
        if text[i] == "{":
            parsed = _parse_brace_set(text, i)
            if parsed is None:
                return None
            values, nxt = parsed
            found.append(values)
            spans.append((i, nxt))
            i = nxt
        else:
            i += 1
    if len(found) != 2:
        return None
    for match in mtm._NUM.finditer(text):
        if not any(start < match.start() and match.end() < end for start, end in spans):
            return None
    return found


def _extract_set_intent(cleaned: str, lower: str) -> MathIntent | None:
    if word_index(lower, "union") != -1:
        op = "set_union"
    elif word_index(lower, "intersection") != -1:
        op = "set_intersection"
    elif word_index(lower, "difference") != -1:
        op = "set_difference"
    else:
        return None
    groups = _brace_sets(cleaned)
    if groups is None:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op=op,
        vec_a=groups[0],
        vec_b=groups[1],
        operation="solve",
    )


def extract_average_speed_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    if "average speed" not in lower and "average velocity" not in lower:
        return None
    from app.services.math.match.units import (
        LENGTH_UNITS,
        QUANTITY_NUMBER,
        TIME_UNITS,
        unit_after_quantity,
    )

    nums = list(QUANTITY_NUMBER.finditer(cleaned))
    if len(nums) != 2:
        return None
    measures: list[tuple[float, str, int]] = []
    for number in nums:
        unit_hit = unit_after_quantity(cleaned, number.end())
        if unit_hit is None:
            return None
        measures.append((float(number.group(0)), unit_hit[0].lower(), unit_hit[1]))
    # A second request or requested output unit needs the model; do not certify
    # the first two numbers as an answer to an unparsed compound instruction.
    if cleaned[measures[-1][2] :].strip(" .?!").lower() not in {"", "please"}:
        return None
    distance: tuple[float, str] | None = None
    duration: tuple[float, str] | None = None
    for value, unit, _end in measures:
        if unit in LENGTH_UNITS:
            distance = value, LENGTH_UNITS[unit]
        elif unit in TIME_UNITS:
            duration = value, TIME_UNITS[unit]
        else:
            return None
    if distance is None or duration is None or duration[0] <= 0:
        return None
    if "average speed" in lower and distance[0] < 0:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="average_speed",
        expr=f"{distance[0]}/{duration[0]}",
        unit_from=distance[1],
        unit_to=duration[1],
        operation="solve",
    )


def _hour_quantities(text: str) -> list[float]:
    lower = text.lower()
    found: list[float] = []
    for match in _NUM.finditer(text):
        after = lower[match.end() :]
        k = 0
        while k < len(after) and after[k].isspace():
            k += 1
        if after.startswith("hour", k):
            found.append(float(match.group(0)))
    return found


def _extract_work_together_intent(cleaned: str, lower: str) -> MathIntent | None:
    if word_index(lower, "together") == -1 and "combined" not in lower:
        return None
    hours = _hour_quantities(cleaned)
    if len(hours) != 2 or hours[0] <= 0 or hours[1] <= 0:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="work_together",
        percent_base=hours[0],
        percent_rate=hours[1],
        operation="solve",
    )


def _extract_mixture_intent(cleaned: str, lower: str) -> MathIntent | None:
    if "% of " in lower:
        return None
    if not any(word_index(lower, word) != -1 for word in ("mix", "mixed", "mixture")):
        return None
    if cleaned.count("%") != 2:
        return None
    volumes: list[float] = []
    percents: list[float] = []
    for match in _NUM.finditer(cleaned):
        after = cleaned[match.end() :].lstrip()
        value = float(match.group(0))
        if after.startswith("%"):
            percents.append(value)
        else:
            volumes.append(value)
    if len(volumes) != 2 or len(percents) != 2:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="mixture",
        vec_a=volumes,
        vec_b=percents,
        operation="solve",
    )


def _extract_twice_as_many_intent(cleaned: str, lower: str) -> MathIntent | None:
    if "twice as many" not in lower and "2 times as many" not in lower:
        return None
    if word_index(lower, "together") == -1:
        return None
    nums = [float(match.group(0)) for match in _NUM.finditer(cleaned)]
    total: float | None = None
    if "twice as many" in lower and len(nums) == 1:
        total = nums[0]
    elif len(nums) == 2 and 2.0 in nums:
        total = nums[0] if nums[1] == 2.0 else nums[1]
        if total == 2.0:
            return None
    if total is None or total <= 0:
        return None
    return MathIntent(
        kind="arithmetic",
        school_op="twice_as_many",
        percent_base=total,
        operation="solve",
    )


def _extract_word_problem_intent(cleaned: str, lower: str) -> MathIntent | None:
    work = _extract_work_together_intent(cleaned, lower)
    if work is not None:
        return work
    mix = _extract_mixture_intent(cleaned, lower)
    if mix is not None:
        return mix
    return _extract_twice_as_many_intent(cleaned, lower)


def _extract_arithmetic_intent(cleaned: str) -> MathIntent | None:
    substituted = substituted_eval_expr(cleaned)
    if substituted is not None:
        return MathIntent(kind="arithmetic", school_op="eval", expr=substituted, operation="solve")
    if mtm.has_equation(cleaned):
        return None
    percent = _extract_percent_or_ratio(cleaned)
    if percent is not None:
        return percent
    from app.services.math.tools.extractors.formulas import (
        extract_arithmetic_formulas,
        extract_infinite_geometric,
    )

    formulas = extract_arithmetic_formulas(cleaned)
    if formulas is not None:
        return formulas
    lower = cleaned.lower()
    interest = _extract_interest_intent(cleaned, lower)
    if interest is not None:
        return interest
    sets = _extract_set_intent(cleaned, lower)
    if sets is not None:
        return sets
    word = _extract_word_problem_intent(cleaned, lower)
    if word is not None:
        return word
    infinite = extract_infinite_geometric(cleaned)
    if infinite is not None:
        return infinite
    sequence = _extract_sequence_intent(cleaned)
    if sequence is not None:
        return sequence
    speed = extract_average_speed_intent(cleaned)
    if speed is not None:
        return speed
    expr = mtm.bare_arithmetic_expr(cleaned)
    if expr is None:
        return None
    return MathIntent(kind="arithmetic", school_op="eval", expr=expr, operation="solve")


def _extract_probability_intent(cleaned: str) -> MathIntent | None:
    from app.services.math.tools.extractors.formulas import extract_probability_formulas

    extra = extract_probability_formulas(cleaned)
    if extra is not None:
        return extra
    lower = cleaned.lower()
    if "binomial" in lower or ("n=" in lower.replace(" ", "") and "p=" in lower.replace(" ", "")):
        empty = MathIntent(kind="probability", school_op="binomial", operation="solve")
        matches = list(_BINOMIAL_PARAM.finditer(cleaned))
        if len(matches) != 3 or {match.group(1).lower() for match in matches} != {"n", "k", "p"}:
            return empty
        try:
            params = {
                match.group(1).lower(): float(Fraction(match.group(2).replace(" ", "")))
                for match in matches
            }
        except (ValueError, ZeroDivisionError, OverflowError):
            return empty
        n, k, p = params["n"], params["k"], params["p"]
        if n is not None and k is not None and p is not None:
            if not n.is_integer() or not k.is_integer():
                return empty
            return MathIntent(
                kind="probability",
                school_op="binomial",
                combo_n=int(n),
                combo_k=int(k),
                percent_base=p,
                operation="solve",
            )
    if "expected value" in lower or "expected value of" in lower:
        if any(cue in lower for cue in ("probabilit", "weight", "p(", "p=")):
            # Explicit weighted distributions need a separate parser; never
            # average outcomes and probabilities together as a raw list.
            return MathIntent(kind="probability", school_op="expected", operation="solve")
        from app.services.math.match.discrete import numeric_data_values

        nums = numeric_data_values(cleaned[lower.index("expected value") + len("expected value") :])
        if nums is not None:
            return MathIntent(
                kind="probability",
                school_op="expected",
                stats_numbers=nums,
                operation="solve",
            )
    return None


# An elastic modulus is not the modulus of a complex number. This extractor
# runs before the physics ones, so without this "the young modulus for a stress
# of 2e7 Pa" was read as |z| and failed as an unparseable expression.
_ELASTIC_MODULUS_RE = re.compile(
    r"\b(?:young(?:'s)?|bulk|shear|elastic|rigidity)\s+modulus\b", re.IGNORECASE
)


def _extract_complex_intent(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    # Before anything else: an elastic modulus is not the modulus of a complex
    # number, and this extractor runs before the physics ones.
    if _ELASTIC_MODULUS_RE.search(cleaned):
        return None
    from app.services.math.tools.extractors.formulas import extract_complex_op

    op = extract_complex_op(cleaned)
    if op is None:
        has_complex_token = "complex" in lower or "i)" in lower or "+ i" in lower or "- i" in lower
        if not has_complex_token and "imaginary" not in lower:
            return None
    if mtm.has_equation(cleaned) and "solve" in lower:
        return None
    expr = cleaned.strip()
    while True:
        for prefix in (
            "simplify",
            "evaluate",
            "compute",
            "modulus of",
            "modulus",
            "magnitude of",
            "magnitude",
            "argument of",
            "argument",
            "arg of",
            "conjugate of",
            "conjugate",
            "polar form of",
            "polar form",
            "polar of",
            "complex",
        ):
            if expr.lower().startswith(prefix + " "):
                expr = expr[len(prefix) :].lstrip()
                break
        else:
            break
    return MathIntent(kind="complex", school_op=op or "eval", expr=expr, operation="solve")


_ODE_START_RE = re.compile(r"dy\s*/\s*dx|d\^?2\s*y\s*/\s*dx\^?2|[A-Za-z]'")


def _ode_equation(cleaned: str) -> str | None:
    """Span from the first derivative mark through the rhs. Linear scan.

    Accepts the bare first-order forms (``dy/dx = 2y``) and the general linear
    ones (``y'' + y = 0``, ``y'' + 3y' + 2y = 0``). Everything between the
    derivative and the ``=`` must be math: ``Find dy/dx if y = x^2`` is a
    derivative ask, not an ODE, and the word ``if`` is what says so.
    """
    from app.services.math.tools.helpers import _strip_trailing_filler

    match = _ODE_START_RE.search(cleaned)
    if match is None:
        return None
    rest = cleaned[match.start() :]
    eq_at = rest.find("=")
    if eq_at == -1:
        return None
    between = rest[:eq_at]
    for token in between.split():
        word = token.strip(".,?!:;()[]").lower()
        if word.isalpha() and len(word) >= 2:
            return None
    return _strip_trailing_filler(rest)


def _extract_taylor_or_ode(cleaned: str) -> MathIntent | None:
    lower = cleaned.lower()
    taylor_ok = (
        "taylor of " in lower or "maclaurin" in lower or ("taylor" in lower and "series" in lower)
    )
    if taylor_ok:
        expr = mtm.graph_expr(cleaned) or cleaned
        n = mtm.number_after(cleaned, "order") or mtm.number_after(cleaned, "degree") or 5
        point = "0"
        if "maclaurin" not in lower and "at " in lower:
            pt = mtm.number_after(cleaned, "at")
            if pt is not None:
                point = f"{pt:g}"
        # pull expr after "of "
        idx = lower.find(" of ")
        if idx != -1:
            rest = cleaned[idx + 4 :]
            for stop in (" at ", " order", " degree", " around"):
                sidx = rest.lower().find(stop)
                if sidx != -1:
                    rest = rest[:sidx]
            expr = rest.strip()
        return MathIntent(
            kind="calculus",
            operation="taylor",
            expr=expr,
            taylor_n=int(n),
            limit_point=point,
            variable="x",
        )
    if "partial" in lower and (
        "partial of " in lower
        or "partial derivative" in lower
        or " wrt" in lower
        or "with respect to" in lower
    ):
        var = "x"
        if "wrt" in lower:
            after = cleaned.lower().find("wrt")
            rest = cleaned[after + 3 :].strip()
            if rest:
                var = rest[0]
        elif "with respect to" in lower:
            after = lower.find("with respect to")
            rest = cleaned[after + len("with respect to") :].strip()
            if rest:
                var = rest[0]
        idx = lower.find(" of ")
        expr = cleaned[idx + 4 :] if idx != -1 else cleaned
        for stop in (" wrt", " with respect"):
            sidx = expr.lower().find(stop)
            if sidx != -1:
                expr = expr[:sidx]
        return MathIntent(
            kind="calculus",
            operation="partial",
            expr=expr.strip(),
            variable=var,
        )
    if "dy/dx" in lower or "'" in cleaned or "dsolve" in lower:
        ode_eq = _ode_equation(cleaned)
        if ode_eq is None:
            return None
        return MathIntent(kind="calculus", operation="dsolve", expr=ode_eq, variable="x")
    return None


SCHOOL_EXTRACTORS: list[Callable[[str], MathIntent | None]] = [
    _extract_unit_intent,
    _extract_coord_intent,
    _extract_vector_intent,
    _extract_taylor_or_ode,
    _extract_trig_intent,
    _extract_probability_intent,
    _extract_complex_intent,
    _extract_arithmetic_intent,
]


def _verified_block_arithmetic(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if (
        intent.school_op == "percent"
        and intent.percent_rate is not None
        and intent.percent_base is not None
    ):
        answer = math_school.percent_of(intent.percent_rate, intent.percent_base)
        lines.append(f"{intent.percent_rate:g}% of {intent.percent_base:g} = {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op in {"percent_increase", "percent_decrease"}
        and intent.percent_rate is not None
        and intent.percent_base is not None
    ):
        if intent.school_op == "percent_increase":
            answer = math_school.percent_increase(intent.percent_base, intent.percent_rate)
            verb = "increased"
        else:
            answer = math_school.percent_decrease(intent.percent_base, intent.percent_rate)
            verb = "decreased"
        lines.append(f"{intent.percent_base:g} {verb} by {intent.percent_rate:g}% = {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op == "percent_is"
        and intent.percent_rate is not None
        and intent.percent_base is not None
    ):
        answer = math_school.percent_is(intent.percent_rate, intent.percent_base)
        lines.append(f"{intent.percent_rate:g} is {answer}% of {intent.percent_base:g}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op == "discount"
        and intent.percent_rate is not None
        and intent.percent_base is not None
    ):
        from app.services.math import formulas as math_formulas

        answer = math_formulas.sale_price(intent.percent_base, intent.percent_rate)
        lines.append(f"{intent.percent_rate:g}% off {intent.percent_base:g} = {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op == "percent_change_from"
        and intent.percent_base is not None
        and intent.percent_rate is not None
    ):
        from app.services.math import formulas as math_formulas

        answer = math_formulas.percent_change_from(intent.percent_base, intent.percent_rate)
        lines.append(
            f"Percent change from {intent.percent_base:g} to {intent.percent_rate:g} = {answer}"
        )
        return _finish_with_answer(lines, answer)
    if intent.school_op in {"direct_proportion", "inverse_proportion"} and intent.stats_numbers:
        from app.services.math import formulas as math_formulas

        if len(intent.stats_numbers) != 3:
            return None
        a, b, c = intent.stats_numbers
        if intent.school_op == "direct_proportion":
            answer = math_formulas.direct_proportion(a, b, c)
        else:
            answer = math_formulas.inverse_proportion(a, b, c)
        lines.append(f"{intent.school_op}: {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op == "round_decimal"
        and intent.percent_base is not None
        and intent.combo_n is not None
    ):
        from app.services.math import formulas as math_formulas

        answer = math_formulas.round_decimal_places(intent.percent_base, intent.combo_n)
        lines.append(f"Rounded: {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op == "round_sigfigs"
        and intent.percent_base is not None
        and intent.combo_n is not None
    ):
        from app.services.math import formulas as math_formulas

        answer = math_formulas.round_significant_figures(intent.percent_base, intent.combo_n)
        lines.append(f"Rounded: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "infinite_gp" and intent.stats_numbers:
        from app.services.math import formulas as math_formulas

        answer = math_formulas.infinite_geometric_sum(intent.stats_numbers)
        lines.append(f"Infinite GP sum = {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op == "present_value"
        and intent.percent_base is not None
        and intent.percent_rate is not None
        and intent.combo_n is not None
    ):
        from app.services.math import formulas as math_formulas

        answer = math_formulas.present_value(
            intent.percent_base, intent.percent_rate, intent.combo_n
        )
        lines.append(f"Present value = {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op == "ratio"
        and intent.percent_rate is not None
        and intent.percent_base is not None
    ):
        answer = math_school.simplify_ratio(intent.percent_rate, intent.percent_base)
        lines.append(f"Simplified ratio: {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op == "ratio_split"
        and intent.percent_base is not None
        and intent.stats_numbers
    ):
        answer = math_school.split_ratio(intent.percent_base, intent.stats_numbers)
        lines.append(f"{intent.percent_base:g} in ratio split = {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op in {"sequence_nth", "sequence_sum"}
        and intent.stats_numbers
        and intent.combo_n is not None
    ):
        if intent.school_op == "sequence_nth":
            answer = math_school.sequence_nth(intent.stats_numbers, intent.combo_n)
            lines.append(f"Term {intent.combo_n} = {answer}")
        else:
            answer = math_school.sequence_sum(intent.stats_numbers, intent.combo_n)
            lines.append(f"Sum of first {intent.combo_n} terms = {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op in {"simple_interest", "compound_interest", "compound_amount"}
        and intent.percent_base is not None
        and intent.percent_rate is not None
        and intent.combo_n is not None
    ):
        principal, rate, years = intent.percent_base, intent.percent_rate, intent.combo_n
        if intent.school_op == "simple_interest":
            answer = math_school.simple_interest(principal, rate, years)
            label = "Simple interest"
        elif intent.school_op == "compound_amount":
            answer = math_school.compound_amount(principal, rate, years)
            label = "Compound amount"
        else:
            answer = math_school.compound_interest(principal, rate, years)
            label = "Compound interest"
        lines.append(f"{label} on {principal:g} at {rate:g}% for {years} years = {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op in {"set_union", "set_intersection", "set_difference"}
        and intent.vec_a is not None
        and intent.vec_b is not None
    ):
        if intent.school_op == "set_union":
            answer = math_school.set_union(intent.vec_a, intent.vec_b)
        elif intent.school_op == "set_intersection":
            answer = math_school.set_intersection(intent.vec_a, intent.vec_b)
        else:
            answer = math_school.set_difference(intent.vec_a, intent.vec_b)
        lines.append(f"{intent.school_op}: {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op == "work_together"
        and intent.percent_base is not None
        and intent.percent_rate is not None
    ):
        answer = math_school.work_together(intent.percent_base, intent.percent_rate)
        lines.append(
            f"Together: {intent.percent_base:g} h and {intent.percent_rate:g} h → {answer}"
        )
        return _finish_with_answer(lines, answer)
    if intent.school_op == "mixture" and intent.vec_a and intent.vec_b and len(intent.vec_a) == 2:
        if len(intent.vec_b) != 2:
            return None
        answer = math_school.mixture_percent(
            intent.vec_a[0], intent.vec_b[0], intent.vec_a[1], intent.vec_b[1]
        )
        lines.append(f"Mixture: {answer}%")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "twice_as_many" and intent.percent_base is not None:
        answer = math_school.twice_as_many(intent.percent_base)
        lines.append(f"Parts: {answer}")
        return _finish_with_answer(lines, answer)
    if not intent.expr:
        return None
    answer = math_school.evaluate_arithmetic(intent.expr)
    if intent.school_op == "average_speed" and intent.unit_from and intent.unit_to:
        answer = format_quantity(answer, f"{intent.unit_from}/{intent.unit_to}")
    lines.append(f"Result: {answer}")
    return _finish_with_answer(lines, answer)


def _verified_block_trig(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if (
        intent.school_op == "sas_area"
        and intent.percent_base is not None
        and intent.percent_rate is not None
        and intent.point_x is not None
    ):
        from app.services.math import formulas as math_formulas

        answer = math_formulas.sas_triangle_area(
            intent.percent_base, intent.percent_rate, intent.point_x
        )
        lines.append(f"SAS area = {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op and intent.percent_base is not None:
        answer = math_school.evaluate_trig_degrees(intent.school_op, intent.percent_base)
        lines.append(f"{intent.school_op}({intent.percent_base:g}°) = {answer}")
        return _finish_with_answer(lines, answer)
    if intent.expr:
        answer = math_school.evaluate_trig_expr(intent.expr)
        lines.append(f"Result: {answer}")
        return _finish_with_answer(lines, answer)
    return None


def _verified_block_coord(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    from app.services.math import formulas as math_formulas

    if (
        intent.school_op == "point_to_line"
        and intent.point_x is not None
        and intent.point_y is not None
        and intent.vec_a
        and len(intent.vec_a) == 3
    ):
        answer = math_formulas.point_to_line(
            intent.point_x, intent.point_y, intent.vec_a[0], intent.vec_a[1], intent.vec_a[2]
        )
        lines.append(f"point_to_line: {answer}")
        return _finish_with_answer(lines, answer)
    if None in (intent.point_x, intent.point_y, intent.x2, intent.y2):
        return None
    x1, y1, x2, y2 = intent.point_x, intent.point_y, intent.x2, intent.y2
    if x1 is None or y1 is None or x2 is None or y2 is None:
        return None
    if intent.school_op == "line":
        answer = math_formulas.line_through(x1, y1, x2, y2)
    elif intent.school_op == "midpoint":
        answer = math_school.coord_midpoint(x1, y1, x2, y2)
    elif intent.school_op == "slope":
        answer = math_school.coord_slope(x1, y1, x2, y2)
    else:
        answer = math_school.coord_distance(x1, y1, x2, y2)
    lines.append(f"{intent.school_op}: {answer}")
    return _finish_with_answer(lines, answer)


def _verified_block_vector(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.vec_a:
        return None
    if intent.school_op == "magnitude":
        answer = math_school.vector_magnitude(intent.vec_a)
    elif intent.school_op == "unit":
        from app.services.math import formulas as math_formulas

        answer = math_formulas.vector_unit(intent.vec_a)
    elif intent.school_op == "dot" and intent.vec_b:
        answer = math_school.vector_dot(intent.vec_a, intent.vec_b)
    elif intent.school_op == "cross" and intent.vec_b:
        answer = math_school.vector_cross(intent.vec_a, intent.vec_b)
    elif intent.school_op == "angle" and intent.vec_b:
        from app.services.math import formulas as math_formulas

        answer = math_formulas.vector_angle_degrees(intent.vec_a, intent.vec_b)
    elif intent.school_op == "projection" and intent.vec_b:
        from app.services.math import formulas as math_formulas

        answer = math_formulas.vector_projection(intent.vec_a, intent.vec_b)
    else:
        return None
    lines.append(f"{intent.school_op}: {answer}")
    return _finish_with_answer(lines, answer)


def _verified_block_probability(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if (
        intent.school_op == "binomial"
        and intent.combo_n is not None
        and intent.combo_k is not None
        and intent.percent_base is not None
    ):
        answer = math_school.binomial_pmf(intent.combo_n, intent.combo_k, intent.percent_base)
        lines.append(f"P(X={intent.combo_k}) = {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "expected" and intent.stats_numbers:
        answer = math_school.expected_value(intent.stats_numbers, None)
        lines.append(f"E[X] = {answer}")
        return _finish_with_answer(lines, answer)
    from app.services.math import formulas as math_formulas

    if (
        intent.school_op == "geometric"
        and intent.combo_k is not None
        and intent.percent_base is not None
    ):
        answer = math_formulas.geometric_pmf(intent.combo_k, intent.percent_base)
        lines.append(f"P(X={intent.combo_k}) = {answer}")
        return _finish_with_answer(lines, answer)
    if (
        intent.school_op == "poisson"
        and intent.combo_k is not None
        and intent.percent_base is not None
    ):
        answer = math_formulas.poisson_pmf(intent.combo_k, intent.percent_base)
        lines.append(f"P(X={intent.combo_k}) = {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "complement" and intent.percent_base is not None:
        answer = math_formulas.complement_probability(intent.percent_base)
        lines.append(f"1-P = {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "bayes" and intent.vec_a and len(intent.vec_a) == 3:
        answer = math_formulas.bayes_probability(intent.vec_a[0], intent.vec_a[1], intent.vec_a[2])
        lines.append(f"P(A|B) = {answer}")
        return _finish_with_answer(lines, answer)
    return None


def _verified_block_complex(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if not intent.expr:
        return None
    from app.services.math import formulas as math_formulas

    if intent.school_op == "modulus":
        answer = math_formulas.complex_modulus(intent.expr)
    elif intent.school_op == "argument":
        answer = math_formulas.complex_argument(intent.expr)
    elif intent.school_op == "conjugate":
        answer = math_formulas.complex_conjugate(intent.expr)
    elif intent.school_op == "polar":
        answer = math_formulas.complex_polar(intent.expr)
    else:
        answer = math_school.evaluate_complex(intent.expr)
    lines.append(f"Result: {answer}")
    return _finish_with_answer(lines, answer)


def _verified_block_unit(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.percent_base is None or not intent.unit_from or not intent.unit_to:
        return None
    answer = math_school.convert_unit(intent.percent_base, intent.unit_from, intent.unit_to)
    lines.append(f"{intent.percent_base:g} {intent.unit_from} = {answer} {intent.unit_to}")
    return _finish_with_answer(lines, format_quantity(answer, intent.unit_to))


def apply_calculus_extension(
    intent: MathIntent, settings: Settings, lines: list[str]
) -> VerifiedMathBlock | None:
    if intent.operation == "taylor" and intent.expr:
        out = math_school.taylor_series(
            intent.expr, intent.variable, intent.limit_point or "0", intent.taylor_n or 5
        )
        lines.append(f"Taylor: {out.latex}")
        return _finish_with_answer(lines, out.latex)
    if (
        intent.operation == "partial"
        and intent.expr
        and intent.school_op
        not in {
            "gradient",
            "directional",
            "divergence",
            "curl",
        }
    ):
        out = math_school.partial_derivative(intent.expr, intent.variable)
        lines.append(f"Partial: {out.latex}")
        return _finish_with_answer(lines, out.latex)
    if intent.operation == "dsolve" and intent.expr:
        out = math_school.solve_ode(intent.expr, intent.variable)
        lines.append(f"ODE: {out.latex}")
        return _finish_with_answer(lines, out.latex)
    if intent.operation == "critical_points" and intent.expr:
        out = math_school.critical_points(intent.expr, intent.variable)
        lines.append(f"Critical points: {out.latex}")
        return _finish_with_answer(lines, out.latex)
    if intent.school_op == "identity" and intent.lhs and intent.rhs:
        answer = math_school.verify_identity(intent.lhs, intent.rhs)
        lines.append("Identity holds.")
        return _finish_with_answer(lines, answer)
    from app.services.math import formulas as math_formulas

    if intent.school_op == "average_value" and intent.expr and intent.integral_lower is not None:
        if intent.integral_upper is None:
            return None
        answer = math_formulas.average_value(
            intent.expr, intent.variable, intent.integral_lower, intent.integral_upper
        )
        lines.append(f"Average value: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "linear_approx" and intent.expr and intent.limit_point is not None:
        answer = math_formulas.linear_approximation(
            intent.expr, intent.variable, intent.limit_point
        )
        lines.append(f"Linear approximation: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "gradient" and intent.expr:
        answer = math_formulas.gradient_of(intent.expr)
        lines.append(f"Gradient: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "directional" and intent.expr and intent.vec_a and intent.vec_b:
        answer = math_formulas.directional_derivative(
            intent.expr, tuple(intent.vec_a), intent.vec_b
        )
        lines.append(f"Directional derivative: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "divergence" and intent.expr:
        answer = math_formulas.divergence_of(intent.expr)
        lines.append(f"Divergence: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "curl" and intent.expr:
        answer = math_formulas.curl_of(intent.expr)
        lines.append(f"Curl: {answer}")
        return _finish_with_answer(lines, answer)
    if intent.school_op == "implicit" and intent.lhs and intent.rhs:
        answer = math_formulas.implicit_derivative(intent.lhs, intent.rhs)
        lines.append(f"dy/dx = {answer}")
        return _finish_with_answer(lines, answer)
    return None


# Any, not MathIntent: math/tools/block/__init__.py's generic dispatch joins
# this registry's Callable type with PHYSICS_BLOCK_BUILDERS's (PhysicsIntent)
# when both are candidates for the same `builder` variable — without this
# explicit annotation, mypy infers the dict's value type from these
# MathIntent-only functions and that narrower type wins the join, which then
# rejects the physics dispatch path entirely.
_SchoolBlockBuilder = Callable[[Any, Settings, list[str]], VerifiedMathBlock | None]

SCHOOL_BLOCK_BUILDERS: dict[str, _SchoolBlockBuilder] = {
    "arithmetic": _verified_block_arithmetic,
    "trig": _verified_block_trig,
    "coord": _verified_block_coord,
    "vector": _verified_block_vector,
    "probability": _verified_block_probability,
    "complex": _verified_block_complex,
    "unit": _verified_block_unit,
}
