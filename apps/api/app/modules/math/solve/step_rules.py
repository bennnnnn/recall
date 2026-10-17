"""The rule behind each worked step, and the number work a student typed.

A step says what to do ("Subtract 25 from both sides"); its rule says why that
is allowed ("Subtraction property of equality"). The rule is read from the
step's label, so every equation trace (linear, quadratic, radical, log, …)
gets one without each builder carrying it.

``3x^2 + 5^2 = 25`` used to start at ``3x^2 + 25 = 25``: the 5² became 25
with no step. ``evaluate_powers_label`` names that move so it is shown.
"""

from __future__ import annotations

import re
from typing import Any

from sympy import Pow, latex, preorder_traversal

# First match wins; a label that names no rule ("Simplify", "Solve") gets none.
_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), rule)
    for pattern, rule in (
        (r"^Add\b.*\bto both sides", "Addition property of equality"),
        (r"^Subtract\b.*\bfrom both sides", "Subtraction property of equality"),
        (r"^Multiply both sides", "Multiplication property of equality"),
        (r"^Divide both sides", "Division property of equality"),
        (
            r"^(?:Square root|Take (?:the )?square roots?)",
            r"Square root property: $x^2 = k \Rightarrow x = \pm\sqrt{k}$",
        ),
        (r"^Raise both sides", "Power property of equality"),
        (r"^Square (?:both sides|again|and isolate)", "Squaring both sides; check every root"),
        (r"^Take\b.*\bof both sides", "Same operation on both sides"),
        (r"^Evaluate\b", r"Exponent: $a^n$ is $a$ multiplied by itself $n$ times"),
        (r"^Expand\b", r"Distributive property: $a(b + c) = ab + ac$"),
        (r"^Collect like terms", "Combine like terms"),
        (
            r"^Set each factor equal to zero",
            r"Zero product property: $ab = 0 \Rightarrow a = 0$ or $b = 0$",
        ),
        (r"^Factor\b", "Factoring"),
        (
            r"^Quadratic formula",
            r"Quadratic formula: $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$",
        ),
        (r"^Discriminant", r"Discriminant: $b^2 - 4ac$"),
        (r"^Use the zero-exponent law", r"Zero exponent: $a^0 = 1$ for $a \ne 0$"),
        (r"^Equal bases", r"Equal bases: $a^m = a^n \Rightarrow m = n$"),
        (r"^Write\b.*\bas a power of", "Rewrite with the same base"),
        (r"^Combine logarithms", r"Product rule for logs: $\log a + \log b = \log(ab)$"),
        (
            r"^Convert to exponential form",
            r"Definition of a logarithm: $\log_b y = x \Leftrightarrow b^x = y$",
        ),
        (
            r"^Split the absolute-value equation",
            r"Absolute value: $|u| = k \Rightarrow u = k$ or $u = -k$",
        ),
        (r"^Check\b", "Substitute back into the original equation"),
    )
)


_INEQUALITY = re.compile(r"<|>|\\le\b|\\ge\b|\\leq\b|\\geq\b|\\lt\b|\\gt\b")


def step_rule(label: str, formula: str = "") -> str | None:
    """The named rule a step uses, or None when it is plain arithmetic.

    The same move on an inequality is a property of inequality, not equality.
    """
    text = label.strip()
    for pattern, rule in _RULES:
        if pattern.search(text):
            if _INEQUALITY.search(formula):
                return rule.replace("property of equality", "property of inequality")
            return rule
    return None


def evaluate_powers_label(*written_sides: Any) -> str | None:
    """``Evaluate $5^{2} = 25$`` for each number raised to a power the student typed."""
    shown: list[str] = []
    seen: set[str] = set()
    for side in written_sides:
        for node in preorder_traversal(side):
            if not isinstance(node, Pow) or not (node.base.is_Number and node.exp.is_Number):
                continue
            tex = rf"{latex(node)} = {latex(node.doit())}"
            if tex not in seen:
                seen.add(tex)
                shown.append(f"${tex}$")
    if not shown:
        return None
    return "Evaluate " + ", ".join(shown)
