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

# 5^2 is shown as 5 · 5; 2^10 is shown only as its value.
_SHOW_REPEATED = 4

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
        (r"^Multiply the numbers", "Multiply before adding (order of operations)"),
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


def evaluate_powers(*written_sides: Any) -> tuple[str, str] | None:
    """The step for numbers raised to a power the student typed: (label, working).

    The label stays plain text: the phone draws a step badge only when the bold
    heading has no maths in it. One power shows its repeated multiplication,
    ``5^{2} = 5 \\cdot 5 = 25``, which the lesson splits one ``=`` per line.
    """
    shown: list[str] = []
    for side in written_sides:
        for node in preorder_traversal(side):
            if not isinstance(node, Pow) or not (node.base.is_Number and node.exp.is_Number):
                continue
            value = latex(node.doit())
            repeated = (
                r" \cdot ".join([latex(node.base)] * int(node.exp))
                if node.exp.is_Integer and 1 < int(node.exp) <= _SHOW_REPEATED and node.base >= 0
                else None
            )
            tex = (
                f"{latex(node)} = {value}"
                if repeated is None
                else f"{latex(node)} = {repeated} = {value}"
            )
            if tex not in shown:
                shown.append(tex)
    if not shown:
        return None
    if len(shown) == 1:
        return "Evaluate the power", shown[0]
    # Several statements on one line; split_equality_chain leaves a ``\quad`` line whole.
    return "Evaluate the powers", r",\quad ".join(
        part.split(" = ")[0] + " = " + part.split(" = ")[-1] for part in shown
    )


def with_powers_evaluated(written_tex: str, side: Any) -> str:
    """The typed side with each number's power swapped for its value: ``2(x + 9)``.

    The swap is on the typed LaTeX. Rebuilding the expression lets SymPy
    distribute and reorder (``18 + 2x``), which hides the next step.
    """
    out = written_tex
    powers = {
        node
        for node in preorder_traversal(side)
        if isinstance(node, Pow) and node.base.is_Number and node.exp.is_Number
    }
    for node in sorted(powers, key=lambda power: -len(latex(power))):
        pattern = r"(?<![\d.])" + re.escape(str(latex(node)))
        value = str(latex(node.doit()))
        out = re.sub(pattern, value.replace("\\", r"\\"), out)
    return out
