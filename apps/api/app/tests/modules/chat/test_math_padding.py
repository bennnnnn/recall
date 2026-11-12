"""A space inside inline maths dollars is trimmed; prices and prose stay as written."""

from __future__ import annotations

import pytest

from app.modules.chat.math_padding import without_math_padding


@pytest.mark.parametrize(
    ("text", "trimmed"),
    [
        # Live 2026-11-06.
        (
            "one factor starts with $2x $ and the other with $ x$:",
            "one factor starts with $2x$ and the other with $x$:",
        ),
        ("Let $ x = 2 $ 3 times", "Let $x = 2$ 3 times"),
        ("$\\frac{1}{2} $ of it", "$\\frac{1}{2}$ of it"),
        ("$ W_{out} $ is the work", "$W_{out}$ is the work"),
        ("price $5 for $ x$ items", "price $5 for $x$ items"),
        # A factorial is maths, not a price ending in "!" (the phone's rule, 2026-11-11).
        ("$ 4! $ ways", "$4!$ ways"),
        ("so $ 4! + 3! $ in all", "so $4! + 3!$ in all"),
    ],
)
def test_padded_maths_is_trimmed(text: str, trimmed: str) -> None:
    assert without_math_padding(text) == trimmed


@pytest.mark.parametrize(
    "text",
    [
        "it costs $5 and $10",
        "pay $38.40 = $ 19.20 total",
        "from $ 80/night for $n$ nights",
        "between $ and the other $ here",
        "code `$ x$` stays",
        "$$ x $$ display",
        "```\n$ x$\n```",
        "> $ x$ quote",
        "    $ x$ indented code",
        "$x$ and $y$ are fine",
    ],
)
def test_prices_prose_code_and_display_stay(text: str) -> None:
    assert without_math_padding(text) == text
