"""Every worked step names its rule, and typed number work gets its own step."""

import pytest

from app.core.config import Settings
from app.modules.math.solve.key_steps import written_side
from app.modules.math.solve.step_rules import evaluate_powers_label, step_rule
from app.modules.math.tools.direct import maybe_direct_math_reply
from app.modules.math.tools.prompt import build_math_augmentation


@pytest.mark.parametrize(
    ("label", "rule"),
    [
        ("Subtract 25 from both sides", "Subtraction property of equality"),
        ("Add $3x$ to both sides", "Addition property of equality"),
        ("Divide both sides by 3", "Division property of equality"),
        ("Multiply both sides by -1", "Multiplication property of equality"),
        ("Take the square root of both sides", "Square root property"),
        ("Expand", "Distributive property"),
        ("Set each factor equal to zero", "Zero product property"),
        ("Quadratic formula", "Quadratic formula"),
        ("Evaluate $5^{2} = 25$", "Exponent"),
    ],
)
def test_step_rule_names_the_property_a_move_uses(label: str, rule: str) -> None:
    named = step_rule(label)
    assert named is not None and named.startswith(rule)


@pytest.mark.parametrize("label", ["Simplify", "Solve", "Domain restrictions"])
def test_step_rule_leaves_plain_arithmetic_unnamed(label: str) -> None:
    assert step_rule(label) is None


def test_step_rule_on_an_inequality_is_a_property_of_inequality() -> None:
    assert step_rule("Divide both sides by -3", r"x \le -2") == "Division property of inequality"


def test_evaluate_powers_label_lists_each_typed_power_once() -> None:
    left = written_side("3x^2 + 5^2", ["x"])
    right = written_side("2^3 + 5^2", ["x"])
    assert left is not None and right is not None
    assert evaluate_powers_label(left[0], right[0]) == "Evaluate $5^{2} = 25$, $2^{3} = 8$"
    plain = written_side("3x^2 + 25", ["x"])
    assert plain is not None and evaluate_powers_label(plain[0]) is None


@pytest.mark.asyncio
async def test_a_typed_power_is_its_own_step_before_the_inverse_moves() -> None:
    query = "3x^2+5^2=25"
    _, verified = await build_math_augmentation(query, Settings(math_tools_enabled=True))
    reply = maybe_direct_math_reply(verified, query)
    assert reply is not None
    steps = [line for line in reply.splitlines() if line.startswith("**") and ". " in line]
    assert steps[0].startswith("**1. Evaluate $5^{2} = 25$** — Exponent")
    assert steps[1].startswith("**2. Subtract 25 from both sides** — Subtraction property")
    assert "$3 x^{2} + 25 = 25$" in reply
    assert r"$x = \pm \sqrt{0}$" in reply
