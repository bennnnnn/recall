"""How many separate things a message asks (``turn_reading.length.asked_parts``)."""

import pytest

from app.modules.turn_reading.length import MANY_PARTS, asked_parts


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("1. Derive the metric.\n2. Find E and L.\n3) Plot the orbit.\n(4) Discuss.", 4),
        # A second list numbered from 1 again asks nothing new.
        ("1. a\n2. b\nThen:\n1. c\n2. d", 2),
        ("Find (a) the speed (b) the time (c) the range", 3),
        ("What is 2.5 times 3?", 0),
        ("1. Only one numbered line", 0),
        ("**1.** Derive it.\n**2.** Plot it.\nQ3. Explain it.", 3),
        # Dates, and numbered lines in pasted code or a log, ask nothing.
        ("Termine:\n12. März Arzt\n13. März Zahnarzt\n14. März Friseur", 0),
        (
            "Why does this fail?\n```\n"
            + "\n".join(f"{n}) PASS t{n}" for n in range(1, 12))
            + "\n```",
            0,
        ),
        ("", 0),
        (None, 0),
    ],
)
def test_asked_parts_counts_numbered_lines_or_labelled_parts(text: str | None, parts: int) -> None:
    assert asked_parts(text) == parts


def test_twenty_numbered_parts_are_many() -> None:
    text = "\n".join(f"{n}. Calculate quantity {n}." for n in range(1, 21))
    assert asked_parts(text) == 20 >= MANY_PARTS
