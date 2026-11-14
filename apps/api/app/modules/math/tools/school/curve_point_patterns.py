"""What a request about a curve's points says: its tangent, gradient, stationary points,
points of inflection or where it rises and falls (``curve_points`` answers them)."""

from __future__ import annotations

import re

from app.services.number_text import FRACTION_OR_DECIMAL as _NUMBER

# The curve's name before its expression: "the curve y =", "f(x) =".
_CURVE = r"(?:the\s+(?:curve|graph|function)\s+)?(?:(?:y|[a-z]\s*\(\s*x\s*\))\s*=\s*)?"
# The same, each run of space read once (possessive), before an expression that ends on a
# mark: a lazy expression beside \s+ and \s* took quartic time on "slope of" and a run of
# spaces. An expression read to the end keeps ``_CURVE``: there "y = " and nothing after it
# leaves the expression empty, where this would read "y =" as the expression.
_CURVE_ONCE = r"(?:the\s++(?:curve|graph|function)\s++)?(?:(?:y|[a-z]\s*+\(\s*+x\s*+\))\s*+=\s*+)?"
# The expression and the point it is taken at, to the end of the request: "x^2 at x = 2",
# "x^3 - 2x at the point (1, -1)".
_AT_POINT = (
    r"(?P<expr>.*?\S)\s++(?:at|where|when)\s++(?:the\s++point\s++)?"
    rf"(?:x\s*+=\s*+(?P<x>{_NUMBER})|\(\s*+(?P<px>{_NUMBER})\s*+,\s*+(?P<py>{_NUMBER})\s*+\))\s*+$"
)
TANGENT = re.compile(
    rf"\b(?P<kind>tangent|normal)(?:\s++line)?\s++(?:to|of|for)\s++{_CURVE_ONCE}{_AT_POINT}",
    re.IGNORECASE,
)
# "the gradient of the curve y = x^3 at x = 2": the derivative there, not a system to solve.
GRADIENT_AT = re.compile(
    r"\b(?:gradient|slope)\s++of\s++(?:the\s++)?(?:(?:curve|graph|function|tangent\s++to)\s*+)?"
    rf"(?:of\s++)?{_CURVE_ONCE}{_AT_POINT}",
    re.IGNORECASE,
)
STATIONARY = re.compile(
    # Not "critical points": those include where dy/dx is undefined, which
    # the critical-point solver looks for and this block does not.
    rf"\b(?:stationary|turning)\s+points?\s+(?:of|for|on)\s+{_CURVE}(?P<expr>.+?)\s*$"
    rf"|\b(?:local\s+)?(?:maximum|max)\s+and\s+(?:local\s+)?(?:minimum|min)(?:\s+points?)?"
    rf"\s+(?:of|for)\s+{_CURVE}(?P<expr2>.+?)\s*$",
    re.IGNORECASE,
)
INFLECTION = re.compile(
    rf"\bpoints?\s+of\s+inflection\s+(?:of|for|on)\s+{_CURVE}(?P<expr>.+?)\s*$"
    rf"|\binflection\s+points?\s+(?:of|for|on)\s+{_CURVE}(?P<expr2>.+?)\s*$",
    re.IGNORECASE,
)
MONOTONIC = re.compile(
    rf"^(?:where|when|for\s+what\s+values\s+of\s+x|on\s+what\s+intervals?)\s++is\s++{_CURVE_ONCE}"
    r"(?P<expr>.*?\S)\s++(?P<way>increasing|decreasing)$"
    rf"|^(?:find\s++)?(?:the\s++)?intervals?\s++(?:where|on\s+which)\s++{_CURVE_ONCE}"
    r"(?P<expr2>.*?\S)\s++is\s++(?P<way2>increasing|decreasing)$",
    re.IGNORECASE,
)
