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
        ("so $ 4!  + 3! $ in all", "so $4!  + 3!$ in all"),
        # A price's "!" before words keeps the price apart from the maths after it.
        ("Today $5! 3 left, then $ x$ more.", "Today $5! 3 left, then $x$ more."),
        # A ratio's colon before a number is maths going on, not the price "$9:" (the
        # textbook run, 2026-11-13: its dollars paired round "is the" and one was shown).
        (
            "Check: $9: 12: 15 $ is the $ 3: 4: 5$ ratio.",
            "Check: $9: 12: 15$ is the $3: 4: 5$ ratio.",
        ),
        ("the ratio $2: 3 $ of boys", "the ratio $2: 3$ of boys"),
        ("so $ 1 : 2 : 3 $ by mass", "so $1 : 2 : 3$ by mass"),
        ("time $ 10:  30 $ then", "time $10:  30$ then"),
        # A colon before words still ends a price's clause: the maths after it pairs alone.
        ("It cost $9: cheap, and $ x$ more.", "It cost $9: cheap, and $x$ more."),
        ("Fees: $10; $ y$ each.", "Fees: $10; $y$ each."),
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
        # A price ending in "!" and a space keeps its clause (review of the factorial fix).
        "Lunch was $5! I paid, so $x$ is mine.",
        "Only $5! $x$ is the count.",
        "It was $5! — and $x$ more.",
        "Only $5! 10 left, $x$ is mine.",
    ],
)
def test_prices_prose_code_and_display_stay(text: str) -> None:
    assert without_math_padding(text) == text
