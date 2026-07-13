"""Pre-stream symbolic math augmentation for chat prompts."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import Settings
from app.models.math_schemas import (
    CircleGeometryBlockSpec,
    CircleGeometryInput,
    EquationInput,
    GeometryBlockSpec,
    GraphBlockSpec,
    GraphSampleInput,
    MathImageExtract,
    MathIntent,
    NewtonMethodInput,
    RectangleGeometryInput,
    RightTriangleGeometryBlockSpec,
    RightTriangleGeometryInput,
    SquareGeometryInput,
    SystemOfEquationsInput,
    TriangleGeometryBlockSpec,
    TriangleGeometryInput,
)
from app.services import math_service

logger = logging.getLogger(__name__)

_DRAW_RECTANGLE = re.compile(
    r"\b(?:draw|show|sketch|visuali[sz]e)\s+(?:a\s+)?rectangle\b",
    re.IGNORECASE,
)

_DRAW_RIGHT_TRIANGLE = re.compile(
    r"\b(?:draw|show|sketch|visuali[sz]e)\s+(?:the\s+)?right\s+triangle\b",
    re.IGNORECASE,
)

_DRAW_SQUARE = re.compile(
    r"\b(?:draw|show|sketch|visuali[sz]e)\s+(?:a\s+)?square\b",
    re.IGNORECASE,
)

_DRAW_CIRCLE = re.compile(
    r"\b(?:draw|show|sketch|visuali[sz]e)\s+(?:a\s+)?circle\b",
    re.IGNORECASE,
)

_DEFAULT_RECT = re.compile(
    r"\b(?:draw|show)\s+(?:a\s+)?rectangle\b",
    re.IGNORECASE,
)

_MATH_KEYWORDS = re.compile(
    r"\b("
    r"solve|simplify|factor|expand|differentiate|derivative|integrate|integral|"
    r"equation|algebra|quadratic|polynomial|"
    r"find the angle|diagonal|rectangle|triangle|circle|geometry|"
    r"radius|diameter|circumference|"
    r"graph|plot|function|y\s*=\s*|"
    r"sqrt|square root|pythagor"
    r")\b",
    re.IGNORECASE,
)

_EQUATION_IN_TEXT = re.compile(
    r"([0-9a-zA-Z+\-*/().\s^]+?)\s*=\s*([0-9a-zA-Z+\-*/().\s^]+)",
)

_RECT_DIMS = re.compile(
    r"(?:rectangle|rect)?\s*(?:is|of|with)?\s*"
    r"(?P<w>\d+(?:\.\d+)?)\s*(?:×|x|\*|\sby\s)\s*(?P<h>\d+(?:\.\d+)?)\s*(?P<unit>cm|m|mm|in|ft|units?)?",
    re.IGNORECASE,
)

_SQUARE_SIDE = re.compile(
    r"\bsquare\b[\s\S]{0,60}?(?:side|edge)\s*(?:=|:)?\s*(?P<s>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

_CIRCLE_RADIUS = re.compile(
    r"\bcircle\b[\s\S]{0,60}?radius\s*(?:=|:|of)?\s*(?P<r>\d+(?:\.\d+)?)"
    r"\s*(?:cm|m|mm|in|ft|units?)?",
    re.IGNORECASE,
)

# A message that's ENTIRELY a coordinate pair (nothing else) is unambiguous
# quick-reply shorthand — e.g. answering "what point?" with "(2,3)". Accepts
# "." as well as "," between the two numbers since that's a common mobile
# keyboard slip for a comma right next to it, and requiring the whole
# message to match (not a substring) keeps this from misfiring on prose
# that merely contains a decimal number in parentheses.
_BARE_COORD_PAIR = re.compile(r"^\(\s*(?P<x>-?\d+(?:\.\d+)?)\s*[,.]\s*(?P<y>-?\d+(?:\.\d+)?)\s*\)$")

_PLOT_POINT = re.compile(
    r"\b(?:plot|mark|graph|show)\s+(?:the\s+)?point\s*\(?\s*"
    r"(?P<x>-?\d+(?:\.\d+)?)\s*,\s*(?P<y>-?\d+(?:\.\d+)?)\s*\)?",
    re.IGNORECASE,
)

_CIRCLE_DIAMETER = re.compile(
    r"\bcircle\b[\s\S]{0,60}?diameter\s*(?:=|:|of)?\s*(?P<d>\d+(?:\.\d+)?)"
    r"\s*(?:cm|m|mm|in|ft|units?)?",
    re.IGNORECASE,
)

_TRI_BASE_HEIGHT = re.compile(
    r"base\s*=\s*(?P<base>\d+(?:\.\d+)?)\s*(?:cm|m|mm|in|ft)?"
    r"[\s\S]{0,80}?height\s*=\s*(?P<height>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

_RIGHT_TRI = re.compile(r"\bright\s+triangle\b", re.IGNORECASE)

_RIGHT_TRI_DIMS = re.compile(
    r"(?P<base>\d+(?:\.\d+)?)\s*(?:×|x|\*|\sby\s)\s*(?P<height>\d+(?:\.\d+)?)\s*(?P<unit>cm|m|mm|in|ft|units?)?",
    re.IGNORECASE,
)

_GRAPH_EXPR = re.compile(
    r"\b(?:graph|plot)\s+(?:y\s*=\s*)?(?P<expr>[0-9a-zA-Z+\-*/().\s^]+)",
    re.IGNORECASE,
)

_CALC_OP = re.compile(
    r"\b(simplify|differentiate|derivative|integrate|integral)\b",
    re.IGNORECASE,
)

_LIMIT_TRIGGER = re.compile(r"\b(?:limit|lim)\b", re.IGNORECASE)

# "[find/evaluate/what is] [the] [limit of] EXPR as VAR (approaches|-> |to) POINT"
# — the leading filler words are consumed by optional non-capturing groups so
# `expr` only ever captures the actual math substring, matching
# _strip_trailing_filler's job for the trailing side.
_LIMIT_AS_APPROACHES = re.compile(
    r"(?:(?:find|evaluate|compute|what\s+is|determine)\s+)?(?:the\s+)?(?:limit\s+of\s+)?"
    r"(?P<expr>.+?)\s+as\s+(?P<var>[a-zA-Z])\s*"
    r"(?:approaches|goes\s+to|tends\s+to|->|→|to)\s*"
    r"(?P<point>-?infinity|-?inf(?:inity)?|-?oo|-?\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)

# Compact form without "as ... approaches": "lim x->0 sin(x)/x", "lim x -> 0 of f(x)".
_LIMIT_COMPACT = re.compile(
    r"\blim\b\s+(?P<var>[a-zA-Z])\s*(?:->|→)\s*"
    r"(?P<point>-?infinity|-?inf|-?oo|-?\d+(?:\.\d+)?)\s+(?:of\s+)?(?P<expr>.+)",
    re.IGNORECASE,
)

# OCR/pasted LaTeX: \lim_{x \to 0} f(x) (braces and backslash-to optional).
_LIMIT_LATEX = re.compile(
    r"\\lim[_\s]*\{?\s*(?P<var>[a-zA-Z])\s*(?:\\to|->|→)\s*"
    r"(?P<point>-?\\infty|-?infinity|-?inf|-?oo|-?\d+(?:\.\d+)?)\}?\s*(?P<expr>.+)?",
    re.IGNORECASE,
)

_SERIES_TRIGGER = re.compile(r"\b(?:series|converge[snt]?|divergen?[ct]?)\b", re.IGNORECASE)

# "[does the] [series/sum] [of] EXPR from VAR=START to END [converge]"
_SERIES_SUM_FROM_TO = re.compile(
    r"(?:sum|series)\s+(?:of\s+)?(?P<expr>.+?)\s+from\s+(?P<var>[a-zA-Z])\s*=\s*"
    r"(?P<start>-?\d+)\s+to\s+(?P<end>infinity|inf|oo|-?\d+)",
    re.IGNORECASE,
)

# OCR/pasted LaTeX: \sum_{n=1}^{\infty} f(n).
_SERIES_LATEX = re.compile(
    r"\\sum[_\s]*\{?\s*(?P<var>[a-zA-Z])\s*=\s*(?P<start>-?\d+)\}?\s*"
    r"\^\{?\s*(?P<end>\\infty|infinity|-?\d+)\}?\s*(?P<expr>.+)?",
    re.IGNORECASE,
)

# _SERIES_SUM_FROM_TO's own "sum|series (of)?" prefix only strips ONE
# leading occurrence — natural phrasing like "does the SERIES sum of EXPR
# from..." has both words, leaving "sum of EXPR" as the captured expr. Strip
# any repeated leading series/sum filler the same way _strip_trailing_filler
# strips trailing filler.
_SERIES_PREFIX_RE = re.compile(
    r"^(?:does\s+)?(?:the\s+)?(?:series|sum)\s+(?:of\s+)?", re.IGNORECASE
)

# Common LaTeX commands/symbols that appear in a pasted or OCR'd limit/series
# expression — _parse_expression's safe-character allowlist rejects any
# backslash outright, so these must be normalized to plain SymPy-parseable
# syntax first. Not exhaustive: an unrecognized command left behind simply
# fails to parse and the caller gracefully falls back to no verified block,
# same as any other unparseable expression.
_LATEX_SYMBOL_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\\infty"), "oo"),
    (re.compile(r"\\pi\b"), "pi"),
    (re.compile(r"\\cdot"), "*"),
    (re.compile(r"\\times"), "*"),
    (re.compile(r"\\div"), "/"),
    (re.compile(r"\\left"), ""),
    (re.compile(r"\\right"), ""),
]
_LATEX_FUNCTION_RE = re.compile(
    r"\\(sin|cos|tan|sec|csc|cot|arcsin|arccos|arctan|sinh|cosh|tanh|log|ln|sqrt|exp|min|max)\b",
    re.IGNORECASE,
)


def _normalize_latex_expr(expr: str) -> str:
    s = expr
    for pattern, replacement in _LATEX_SYMBOL_SUBS:
        s = pattern.sub(replacement, s)
    s = _LATEX_FUNCTION_RE.sub(lambda m: m.group(1), s)
    return s


def _strip_series_prefix(expr: str) -> str:
    s = expr.strip()
    prev = None
    while prev != s:
        prev = s
        s = _SERIES_PREFIX_RE.sub("", s).strip()
    return s


_NEWTON_TRIGGER = re.compile(
    r"\bnewton'?s?\s+method\b|\bnumerically\s+(?:solve|approximate)\b"
    r"|\bfind\s+the\s+root\s+of\b|\bnumerical\s+root\b",
    re.IGNORECASE,
)

# Starting point for the iteration — "starting at x0 = 2", "initial guess of
# 1", "near x=2", "guess 1". Matched and stripped out of the text BEFORE
# equation extraction runs, so e.g. "x0 = 2" is never mistaken for a second
# equation clause.
_NEWTON_GUESS = re.compile(
    r"(?:with\s+)?(?:starting\s+(?:at|near|with)?\s*|initial\s+guess\s+(?:of\s+)?|near\s+|guess\s+)"
    r"(?:x0\s*=\s*|x\s*=\s*)?(?P<guess>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

# Newton-specific leading phrasing — _strip_leading_filler (math_service.py)
# only knows the generic "solve"/"what is" triggers, not "newton's method"/
# "find the root of"/"numerically solve", so those need stripping here
# before try_extract_equations_from_text runs on the remaining text.
_NEWTON_PREFIX_RE = re.compile(
    r"^\s*(?:please\s+)?(?:can\s+you\s+|could\s+you\s+)?(?:use\s+)?"
    r"newton'?s?\s+method\s+(?:to\s+find\s+the\s+root\s+of\s+|for\s+|on\s+)?"
    r"|^\s*(?:please\s+)?numerically\s+(?:solve|approximate)\s+"
    r"|^\s*(?:please\s+)?find\s+the\s+root\s+of\s+",
    re.IGNORECASE,
)

_DEFAULT_NEWTON_GUESS = 1.0


_TRAILING_FILLER_RE = re.compile(
    r"\s+(?:please|now|thanks?|thank\s+you|for\s+me|to\s+me|real\s+quick|quickly|briefly)\.?\s*$",
    re.IGNORECASE,
)


def _strip_trailing_filler(expr: str) -> str:
    """`_GRAPH_EXPR`/the calculus expr-match are greedy captures of everything
    after the trigger word, so natural phrasing like "graph x^2 please" or
    "differentiate x^2 for me" sweeps the trailing words into the
    "expression" — which then fails to parse and silently disables the
    verified-math augmentation for phrasing a real user would actually type."""
    s = expr.strip()
    # A conjunction essentially never appears inside a math expression
    # itself — anything from " and "/" then " onward is a new clause of
    # natural language (e.g. "sin(x) and explain it"), not part of the expr.
    s = re.split(r"\s+(?:and|then)\s+", s, maxsplit=1, flags=re.IGNORECASE)[0]
    prev = None
    while prev != s:
        prev = s
        s = _TRAILING_FILLER_RE.sub("", s).strip()
    return s


def needs_symbolic_math(text: str, *, has_image_attachment: bool = False) -> bool:
    cleaned = text.strip()
    if not cleaned and not has_image_attachment:
        return False
    from app.services.math_image_extract import is_math_camera_prompt

    if has_image_attachment and is_math_camera_prompt(cleaned):
        return True
    if (
        _DRAW_RECTANGLE.search(cleaned)
        or _DRAW_RIGHT_TRIANGLE.search(cleaned)
        or _DRAW_SQUARE.search(cleaned)
        or _DRAW_CIRCLE.search(cleaned)
    ):
        return True
    if has_image_attachment and _MATH_KEYWORDS.search(cleaned):
        return True
    if _EQUATION_IN_TEXT.search(cleaned) and _MATH_KEYWORDS.search(cleaned):
        return True
    if _RECT_DIMS.search(cleaned):
        return True
    if _CIRCLE_RADIUS.search(cleaned) or _CIRCLE_DIAMETER.search(cleaned):
        return True
    if _BARE_COORD_PAIR.match(cleaned) or _PLOT_POINT.search(cleaned):
        return True
    if _GRAPH_EXPR.search(cleaned):
        return True
    if _CALC_OP.search(cleaned):
        return True
    if (
        _LIMIT_LATEX.search(cleaned)
        or _LIMIT_COMPACT.search(cleaned)
        or (_LIMIT_TRIGGER.search(cleaned) and _LIMIT_AS_APPROACHES.search(cleaned))
    ):
        return True
    if _SERIES_LATEX.search(cleaned) or (
        (_SERIES_TRIGGER.search(cleaned) or re.search(r"\bsum\b", cleaned, re.IGNORECASE))
        and _SERIES_SUM_FROM_TO.search(cleaned)
    ):
        return True
    if _NEWTON_TRIGGER.search(cleaned):
        return True
    if re.search(r"\bsolve\b", cleaned, re.IGNORECASE) and _EQUATION_IN_TEXT.search(cleaned):
        return True
    return bool(_MATH_KEYWORDS.search(cleaned) and _EQUATION_IN_TEXT.search(cleaned))


def extract_math_intent(text: str) -> MathIntent | None:
    cleaned = text.strip()
    if not cleaned:
        return None

    rect = _RECT_DIMS.search(cleaned)
    if rect:
        unit = (rect.group("unit") or "cm").lower()
        if unit.startswith("unit"):
            unit = "units"
        return MathIntent(
            kind="rectangle",
            width=float(rect.group("w")),
            height=float(rect.group("h")),
            unit=unit,
            operation="solve",
            wants_diagonal=bool(re.search(r"\bdiagonal\b", cleaned, re.IGNORECASE)),
            wants_angle=bool(re.search(r"\bangle\b", cleaned, re.IGNORECASE)),
            wants_area=bool(re.search(r"\barea\b", cleaned, re.IGNORECASE)),
            wants_perimeter=bool(re.search(r"\bperimeter\b", cleaned, re.IGNORECASE)),
        )

    if _DEFAULT_RECT.search(cleaned):
        return MathIntent(kind="rectangle", width=6, height=4, unit="cm", operation="solve")

    if re.search(r"\bsquare\b", cleaned, re.IGNORECASE):
        side_match = _SQUARE_SIDE.search(cleaned)
        if side_match:
            side = float(side_match.group("s"))
            return MathIntent(
                kind="square", side=side, width=side, height=side, unit="cm", operation="solve"
            )
        equal = re.search(
            r"(?P<s>\d+(?:\.\d+)?)\s*(?:×|x|\*|\sby\s)\s*(?P=s)\s*(?:cm|m|mm|in|ft)?",
            cleaned,
            re.IGNORECASE,
        )
        if equal:
            side = float(equal.group("s"))
            return MathIntent(
                kind="square", side=side, width=side, height=side, unit="cm", operation="solve"
            )
        return MathIntent(kind="square", side=5, width=5, height=5, unit="cm", operation="solve")

    if re.search(r"\bcircle\b", cleaned, re.IGNORECASE):
        wants_area = bool(re.search(r"\barea\b", cleaned, re.IGNORECASE))
        wants_circumference = bool(re.search(r"\bcircumference\b", cleaned, re.IGNORECASE))
        radius_match = _CIRCLE_RADIUS.search(cleaned)
        if radius_match:
            return MathIntent(
                kind="circle",
                radius=float(radius_match.group("r")),
                unit="cm",
                operation="solve",
                wants_area=wants_area,
                wants_circumference=wants_circumference,
            )
        diameter_match = _CIRCLE_DIAMETER.search(cleaned)
        if diameter_match:
            return MathIntent(
                kind="circle",
                radius=float(diameter_match.group("d")) / 2,
                unit="cm",
                operation="solve",
                wants_diameter=True,
                wants_area=wants_area,
                wants_circumference=wants_circumference,
            )
        return MathIntent(kind="circle", radius=5, unit="cm", operation="solve")

    if _RIGHT_TRI.search(cleaned):
        rt_dims = _RIGHT_TRI_DIMS.search(cleaned)
        if rt_dims:
            unit = (rt_dims.group("unit") or "cm").lower()
            if unit.startswith("unit"):
                unit = "units"
            return MathIntent(
                kind="right_triangle",
                base=float(rt_dims.group("base")),
                height=float(rt_dims.group("height")),
                unit=unit,
                operation="solve",
            )
        return MathIntent(kind="right_triangle", base=6, height=4, unit="cm", operation="solve")

    tri = _TRI_BASE_HEIGHT.search(cleaned)
    if tri:
        return MathIntent(
            kind="triangle",
            base=float(tri.group("base")),
            height=float(tri.group("height")),
            unit="cm",
            operation="solve",
        )

    if re.search(r"\btriangle\b", cleaned, re.IGNORECASE) and re.search(
        r"\b(?:area|draw|visuali[sz]e|sketch)\b", cleaned, re.IGNORECASE
    ):
        return MathIntent(kind="triangle", base=8, height=5, unit="cm", operation="solve")

    bare_point = _BARE_COORD_PAIR.match(cleaned)
    point_match = bare_point or _PLOT_POINT.search(cleaned)
    if point_match:
        return MathIntent(
            kind="point",
            point_x=float(point_match.group("x")),
            point_y=float(point_match.group("y")),
            operation="graph",
        )

    graph = _GRAPH_EXPR.search(cleaned)
    if graph:
        expr = _strip_trailing_filler(graph.group("expr")).replace("^", "**")
        return MathIntent(kind="graph", expr=expr, operation="graph")

    calc = _CALC_OP.search(cleaned)
    if calc:
        op_word = calc.group(1).lower()
        calc_op: Literal["simplify", "differentiate", "integrate"] = (
            "differentiate" if op_word in {"differentiate", "derivative"} else "integrate"
        )
        if op_word == "simplify":
            calc_op = "simplify"
        expr_match = re.search(
            r"(?:simplify|differentiate|derivative|integrate|integral)\s+(.+)$", cleaned, re.I
        )
        expr = _strip_trailing_filler(expr_match.group(1)) if expr_match else cleaned
        return MathIntent(kind="calculus", expr=expr, operation=calc_op)

    limit_match = (
        _LIMIT_LATEX.search(cleaned)
        or _LIMIT_COMPACT.search(cleaned)
        or (_LIMIT_TRIGGER.search(cleaned) and _LIMIT_AS_APPROACHES.search(cleaned))
    )
    if limit_match:
        expr_raw = limit_match.group("expr") or ""
        expr = _normalize_latex_expr(_strip_trailing_filler(expr_raw)).replace("^", "**")
        point = limit_match.group("point").lstrip("\\")
        if expr:
            return MathIntent(
                kind="limit",
                expr=expr,
                variable=limit_match.group("var"),
                limit_point=point,
                operation="limit",
            )

    series_match = _SERIES_LATEX.search(cleaned) or (
        (_SERIES_TRIGGER.search(cleaned) or re.search(r"\bsum\b", cleaned, re.IGNORECASE))
        and _SERIES_SUM_FROM_TO.search(cleaned)
    )
    if series_match:
        expr_raw = series_match.group("expr") or ""
        expr = _normalize_latex_expr(
            _strip_series_prefix(_strip_trailing_filler(expr_raw))
        ).replace("^", "**")
        end = series_match.group("end").lstrip("\\")
        if expr:
            return MathIntent(
                kind="series",
                expr=expr,
                variable=series_match.group("var"),
                series_start=series_match.group("start"),
                series_end=end,
                operation="series",
            )

    if _NEWTON_TRIGGER.search(cleaned):
        guess_match = _NEWTON_GUESS.search(cleaned)
        guess = float(guess_match.group("guess")) if guess_match else _DEFAULT_NEWTON_GUESS
        text_for_eq = cleaned
        if guess_match:
            text_for_eq = text_for_eq[: guess_match.start()] + text_for_eq[guess_match.end() :]
        text_for_eq = _NEWTON_PREFIX_RE.sub("", text_for_eq).strip()
        newton_pairs = math_service.try_extract_equations_from_text(text_for_eq)
        if newton_pairs:
            lhs, rhs = newton_pairs[0]
            rhs_is_zero = rhs.strip() in ("0", "0.0")
            expr = lhs if rhs_is_zero else f"({lhs})-({rhs})"
            variables = math_service._guess_variables(f"{lhs} {rhs}")
            var = variables[0] if variables else "x"
            return MathIntent(
                kind="numerical_method",
                expr=expr,
                variable=var,
                newton_guess=guess,
                operation="newton",
            )

    eq_pairs = math_service.try_extract_equations_from_text(cleaned)
    if len(eq_pairs) >= 2:
        # BUG FIX (most severe correctness bug found in the audit): this
        # used to fall through to the single-equation branch below, which
        # only ever looked at the FIRST clause and answered with the same
        # "verified, do NOT recompute" confidence as a fully correct
        # response — silently discarding every other equation in the system.
        all_text = " ".join(f"{lhs} {rhs}" for lhs, rhs in eq_pairs)
        variables = math_service._guess_variables(all_text)
        return MathIntent(
            kind="system",
            system_equations=eq_pairs[:4],
            system_variables=variables,
            operation="solve",
        )
    if len(eq_pairs) == 1:
        lhs, rhs = eq_pairs[0]
        variables = math_service._guess_variables(lhs + rhs)
        return MathIntent(
            kind="equation",
            lhs=lhs,
            rhs=rhs,
            operation="solve",
            variable=variables[0] if variables else "x",
        )

    return None


@dataclass(frozen=True)
class VerifiedMathBlock:
    """The system-prompt hint text plus the exact fence (if any) it asked
    the model to reuse verbatim — canonical_fence lets a post-stream check
    correct the model's actual output rather than only trusting compliance."""

    text: str
    canonical_fence: dict[str, Any] | None = None


def _build_verified_block(intent: MathIntent, settings: Settings) -> VerifiedMathBlock | None:
    lines: list[str] = [
        "Symbolic math results (verified by SymPy — use these exact values in your answer):"
    ]

    try:
        if intent.kind == "equation" and intent.lhs and intent.rhs:
            eq = EquationInput(
                lhs=intent.lhs[: settings.math_max_expr_length],
                rhs=intent.rhs[: settings.math_max_expr_length],
                variables=[intent.variable],
            )
            result = math_service.solve_equation(eq)
            lines.extend(result.steps)
            lines.append(
                "Emit each formula as INLINE $...$ math — do NOT wrap math in "
                "backticks (`` `$...$` `` renders as raw code) and do NOT use "
                "```math block fences for step equations (they render late, "
                "leaving blank gaps during streaming). Inline $...$ renders in "
                "sync with the step text. Do NOT recompute the solutions. Show "
                "worked steps by COPYING the verified steps above verbatim — do "
                "NOT derive intermediate algebra yourself. Keep any spacing "
                "(e.g. \\quad) INSIDE the $...$ math delimiters so it renders."
            )
            return VerifiedMathBlock(text="\n".join(lines))

        if intent.kind == "system" and intent.system_equations:
            capped_equations = [
                (
                    lhs[: settings.math_max_expr_length],
                    rhs[: settings.math_max_expr_length],
                )
                for lhs, rhs in intent.system_equations
            ]
            sys_input = SystemOfEquationsInput(
                equations=capped_equations,
                variables=intent.system_variables or ["x", "y"],
            )
            sys_result = math_service.solve_system(sys_input)
            lines.extend(sys_result.steps)
            lines.append(
                "Emit each formula as INLINE $...$ math — do NOT wrap math in "
                "backticks (`` `$...$` `` renders as raw code). Do NOT recompute "
                "the solutions. Show worked steps by COPYING the verified steps "
                "above verbatim — do NOT derive intermediate algebra yourself."
            )
            return VerifiedMathBlock(text="\n".join(lines))

        if intent.kind == "numerical_method" and intent.expr and intent.newton_guess is not None:
            newton_input = NewtonMethodInput(
                expr=intent.expr[: settings.math_max_expr_length],
                variable=intent.variable,
                initial_guess=intent.newton_guess,
            )
            newton_result = math_service.newton_method(newton_input)
            lines.append(
                f"Newton's method for {newton_input.expr} = 0, x0 = {newton_input.initial_guess}:"
            )
            for step in newton_result.iterations:
                lines.append(f"  n={step.n}: x_{step.n} = {step.x_n}, f(x_{step.n}) = {step.f_x_n}")
            if newton_result.converged:
                lines.append(
                    f"Converged after {newton_result.iterations_used} iterations: root ≈ {newton_result.root}"
                )
            else:
                lines.append(
                    f"Did not converge within {newton_result.iterations_used} iterations "
                    "(the derivative may have vanished, or more iterations are needed) — "
                    "do NOT present a root as found."
                )
            lines.append(
                "Do NOT recompute or invent different iteration values. Show the "
                "worked steps by COPYING the verified iteration table above verbatim."
            )
            return VerifiedMathBlock(text="\n".join(lines))

        if intent.kind == "rectangle" and intent.width and intent.height:
            rect_geo = math_service.rectangle_geometry(
                RectangleGeometryInput(width=intent.width, height=intent.height, unit=intent.unit)
            )
            lines.append(
                f"Rectangle: width={rect_geo.width:g} {rect_geo.unit} "
                f"height={rect_geo.height:g} {rect_geo.unit} "
                f"diagonal={rect_geo.diagonal:g} angle={rect_geo.angle_deg:g}°"
            )
            # Only annotate the diagram with what was actually asked for —
            # e.g. "rectangle area 4 by 5" should draw area, not an
            # unrequested diagonal + angle. If nothing specific was asked,
            # default to the diagonal (a reasonable generic illustration)
            # without the angle number, since a bare "draw a rectangle" isn't
            # asking about any particular angle.
            show_area = intent.wants_area
            show_perimeter = intent.wants_perimeter
            show_diagonal = (
                intent.wants_diagonal or intent.wants_angle or not (show_area or show_perimeter)
            )
            show_angle = intent.wants_angle
            spec = GeometryBlockSpec(
                type="rectangle",
                width=rect_geo.width,
                height=rect_geo.height,
                unit=rect_geo.unit,
                show_diagonal=show_diagonal,
                show_angle=show_angle,
                show_area=show_area,
                show_perimeter=show_perimeter,
                diagonal=rect_geo.diagonal,
                angle_deg=rect_geo.angle_deg,
                area=rect_geo.area,
                perimeter=rect_geo.perimeter,
                labels=rect_geo.labels,
            )
            lines.append(
                "When a diagram helps, emit ONLY this fence (adjust labels if needed):\n"
                f"```geometry\n{json.dumps(spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute diagonal, angle, area, or perimeter.")
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=spec.model_dump())

        if intent.kind == "square" and (intent.side or intent.width):
            side = intent.side or intent.width or 5
            square_geo = math_service.square_geometry(
                SquareGeometryInput(side=side, unit=intent.unit)
            )
            lines.append(
                f"Square: side={square_geo.side:g} {square_geo.unit} "
                f"diagonal={square_geo.diagonal:g} {square_geo.unit} "
                f"area={square_geo.area:g} {square_geo.unit}² "
                f"perimeter={square_geo.perimeter:g} {square_geo.unit}"
            )
            spec = GeometryBlockSpec(
                type="square",
                side=square_geo.side,
                width=square_geo.side,
                height=square_geo.side,
                unit=square_geo.unit,
                show_diagonal=True,
                show_area=True,
                show_perimeter=True,
                diagonal=square_geo.diagonal,
                area=square_geo.area,
                perimeter=square_geo.perimeter,
                labels=square_geo.labels,
            )
            lines.append(
                "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
                f"```geometry\n{json.dumps(spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute diagonal, area, or perimeter.")
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=spec.model_dump())

        if intent.kind == "circle" and intent.radius:
            circle_geo = math_service.circle_geometry(
                CircleGeometryInput(radius=intent.radius, unit=intent.unit)
            )
            lines.append(
                f"Circle: radius={circle_geo.radius:g} {circle_geo.unit} "
                f"diameter={circle_geo.diameter:g} {circle_geo.unit} "
                f"area={circle_geo.area:.2f} {circle_geo.unit}² "
                f"circumference={circle_geo.circumference:.2f} {circle_geo.unit}"
            )
            circle_spec = CircleGeometryBlockSpec(
                type="circle",
                radius=circle_geo.radius,
                unit=circle_geo.unit,
                show_diameter=intent.wants_diameter,
                show_area=intent.wants_area,
                show_circumference=intent.wants_circumference,
                diameter=circle_geo.diameter,
                area=circle_geo.area,
                circumference=circle_geo.circumference,
                labels=circle_geo.labels,
            )
            lines.append(
                "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
                f"```geometry\n{json.dumps(circle_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute diameter, area, or circumference.")
            return VerifiedMathBlock(
                text="\n".join(lines), canonical_fence=circle_spec.model_dump()
            )

        if intent.kind == "triangle" and intent.base and intent.height:
            tri_geo = math_service.triangle_geometry(
                TriangleGeometryInput(base=intent.base, height=intent.height, unit=intent.unit)
            )
            lines.append(
                f"Triangle: base={tri_geo.base:g} {tri_geo.unit} "
                f"height={tri_geo.height:g} {tri_geo.unit} area={tri_geo.area:g} {tri_geo.unit}²"
            )
            tri_spec = TriangleGeometryBlockSpec(
                type="triangle",
                base=tri_geo.base,
                height=tri_geo.height,
                unit=tri_geo.unit,
                show_labels=True,
                area=tri_geo.area,
                labels=tri_geo.labels,
            )
            lines.append(
                "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
                f"```geometry\n{json.dumps(tri_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute area.")
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=tri_spec.model_dump())

        if intent.kind == "right_triangle" and intent.base and intent.height:
            rt_geo = math_service.right_triangle_geometry(
                RightTriangleGeometryInput(base=intent.base, height=intent.height, unit=intent.unit)
            )
            lines.append(
                f"Right triangle: base={rt_geo.base:g} {rt_geo.unit} "
                f"height={rt_geo.height:g} {rt_geo.unit} "
                f"hypotenuse={rt_geo.hypotenuse:g} {rt_geo.unit} "
                f"area={rt_geo.area:g} {rt_geo.unit}²"
            )
            rt_spec = RightTriangleGeometryBlockSpec(
                type="right_triangle",
                base=rt_geo.base,
                height=rt_geo.height,
                unit=rt_geo.unit,
                show_labels=True,
                show_hypotenuse=True,
                show_angle=True,
                hypotenuse=rt_geo.hypotenuse,
                area=rt_geo.area,
                labels=rt_geo.labels,
            )
            lines.append(
                "When a diagram helps, emit ONLY this fence (NEVER ```json):\n"
                f"```geometry\n{json.dumps(rt_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            lines.append("Do NOT recompute hypotenuse or area.")
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=rt_spec.model_dump())

        if intent.kind == "point" and intent.point_x is not None and intent.point_y is not None:
            px, py = intent.point_x, intent.point_y
            point_spec = GraphBlockSpec(
                expr=f"({px:g}, {py:g})",
                title=f"Point ({px:g}, {py:g})",
                x_min=px - 5,
                x_max=px + 5,
                points=[[px, py]],
            )
            lines.append(f"Point: ({px:g}, {py:g})")
            lines.append(
                "When a diagram helps, emit ONLY this fence (NEVER ```json). Do NOT "
                "invent a line, function, or extra points through it — the user asked "
                "to mark this one coordinate, nothing else:\n"
                f"```graph\n{json.dumps(point_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=point_spec.model_dump())

        if intent.kind == "graph" and intent.expr:
            sample = math_service.sample_function(
                GraphSampleInput(
                    expr=intent.expr[: settings.math_max_expr_length],
                    variable=intent.variable,
                    x_min=-10,
                    x_max=10,
                    n=settings.math_graph_max_points,
                )
            )
            # Only attach segments when a real gap was detected (>1 segment)
            # — the overwhelmingly common case has none, and duplicating
            # every point into a redundant single-segment list would bloat
            # every graph fence for no benefit.
            has_discontinuity = len(sample.segments) > 1
            graph_spec = GraphBlockSpec(
                expr=sample.expr,
                variable=sample.variable,
                x_min=sample.x_min,
                x_max=sample.x_max,
                points=sample.points,
                segments=sample.segments if has_discontinuity else [],
            )
            lines.append(f"Function samples for {sample.expr}: {len(sample.points)} points.")
            if has_discontinuity:
                lines.append(
                    f"NOTE: {sample.expr} has a discontinuity in this range (e.g. a vertical "
                    "asymptote) — the sampled points are split into "
                    f"{len(sample.segments)} segments; do not describe it as a single "
                    "continuous curve."
                )
            lines.append(
                "When a plot helps, emit ONLY this fence:\n"
                f"```graph\n{json.dumps(graph_spec.model_dump(), separators=(',', ':'))}\n```"
            )
            return VerifiedMathBlock(text="\n".join(lines), canonical_fence=graph_spec.model_dump())

        if intent.kind == "calculus" and intent.expr and intent.operation:
            if intent.operation == "simplify":
                out = math_service.simplify_expression(intent.expr, intent.variable)
            elif intent.operation == "differentiate":
                out = math_service.differentiate_expression(intent.expr, intent.variable)
            elif intent.operation == "integrate":
                out = math_service.integrate_expression(intent.expr, intent.variable)
            else:
                return None
            if not out.solved:
                lines.append(
                    f"SymPy could not find a closed-form result (got: {out.latex}). "
                    "Do NOT claim this as a verified answer — tell the user no closed "
                    "form was found, or explain why the integral is hard, instead of "
                    "asserting a solution."
                )
                return VerifiedMathBlock(text="\n".join(lines))
            lines.append(f"Result: {out.latex}")
            lines.append("Do NOT recompute. Explain in plain language with $...$ for formulas.")
            return VerifiedMathBlock(text="\n".join(lines))

        if intent.kind == "limit" and intent.expr and intent.limit_point is not None:
            limit_out = math_service.compute_limit(intent.expr, intent.variable, intent.limit_point)
            lines.append(f"Result: {limit_out.latex}")
            if limit_out.is_infinite:
                lines.append(
                    "This limit is infinite (or does not exist as a finite two-sided "
                    "value) — render it as \\infty, do not treat it as an ordinary "
                    "finite number."
                )
            lines.append("Do NOT recompute. Explain in plain language with $...$ for formulas.")
            return VerifiedMathBlock(text="\n".join(lines))

        if (
            intent.kind == "series"
            and intent.expr
            and intent.series_start is not None
            and intent.series_end is not None
        ):
            series_out = math_service.evaluate_series_sum(
                intent.expr, intent.variable, intent.series_start, intent.series_end
            )
            lines.append(f"Result: {series_out.latex}")
            if series_out.is_convergent is not None:
                lines.append(
                    f"Convergent: {series_out.is_convergent}"
                    + (
                        f" (absolutely convergent: {series_out.is_absolutely_convergent})"
                        if series_out.is_absolutely_convergent is not None
                        else ""
                    )
                    + "."
                )
            if series_out.is_infinite:
                lines.append(
                    "This series diverges to infinity — render it as \\infty, do not "
                    "treat it as an ordinary finite number."
                )
            lines.append("Do NOT recompute. Explain in plain language with $...$ for formulas.")
            return VerifiedMathBlock(text="\n".join(lines))
    except math_service.MathServiceError as exc:
        logger.info("math_tools skipped: %s", exc)
        return None
    except Exception:
        logger.exception("math_tools failed")
        return None

    return None


def _inject_before_last_user(messages: list[dict[str, str]], block: str) -> list[dict[str, str]]:
    augmented = list(messages)
    insert_at = len(augmented)
    for index in range(len(augmented) - 1, -1, -1):
        if augmented[index].get("role") == "user":
            insert_at = index
            break
    augmented.insert(insert_at, {"role": "system", "content": block})
    return augmented


async def augment_prompt_messages(
    messages: list[dict[str, str]],
    user_content: str,
    settings: Settings,
    *,
    has_image_attachment: bool = False,
    image_math_extract: MathImageExtract | None = None,
) -> tuple[list[dict[str, str]], VerifiedMathBlock | None]:
    if not settings.math_tools_enabled:
        return messages, None
    if not needs_symbolic_math(user_content, has_image_attachment=has_image_attachment):
        return messages, None

    if image_math_extract is not None:
        # OCR already produced a Pydantic-validated equation — use it directly
        # instead of re-parsing the stringified "lhs = rhs" text back through
        # try_extract_equations_from_text's restricted character-class regex,
        # which mangles unicode symbols, commas, and abs-value bars a real
        # photographed equation can contain. variables always has >=1 entry
        # (schema default_factory=["x"]), so this is the model's best guess
        # even when the image genuinely used "x".
        intent: MathIntent | None = MathIntent(
            kind="equation",
            lhs=image_math_extract.lhs,
            rhs=image_math_extract.rhs,
            operation="solve",
            variable=image_math_extract.variables[0],
        )
    else:
        intent = extract_math_intent(user_content)
    if intent is None and has_image_attachment:
        lines = [
            "The user attached an image that may contain a math problem. "
            "Extract the equation as lhs/rhs if possible, then explain using verified reasoning. "
            "Use $...$ for formulas and ```geometry / ```graph JSON fences for diagrams."
        ]
        return _inject_before_last_user(messages, "\n".join(lines)), None

    if intent is None:
        return messages, None

    verified = await _build_verified_block_async(intent, settings)
    if not verified:
        return messages, None
    return _inject_before_last_user(messages, verified.text), verified


async def _build_verified_block_async(
    intent: MathIntent, settings: Settings
) -> VerifiedMathBlock | None:
    """Run the sync, CPU-bound SymPy work off the event loop with a hard timeout.

    ``_build_verified_block`` calls into SymPy's ``solve``/``integrate``/etc.,
    which are synchronous and can take arbitrarily long on a pathological
    expression. Without offloading, that would stall every concurrent chat
    stream on this worker's single event loop.
    """
    try:
        async with asyncio.timeout(settings.math_solve_timeout_seconds):
            return await asyncio.to_thread(_build_verified_block, intent, settings)
    except TimeoutError:
        logger.warning(
            "math_tools solve timed out after %ss for kind=%s",
            settings.math_solve_timeout_seconds,
            intent.kind,
        )
        return None
