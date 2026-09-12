"""Bare subtraction must not need conversational scaffolding."""

import pytest

from app.core.config import Settings
from app.services import math_tools
from app.services.math_tools.direct import maybe_direct_math_reply


@pytest.mark.parametrize(
    "text,expected",
    [("2-6", "-4"), ("2 - 6", "-4"), ("2−6", "-4"), ("-2-6", "-8"), ("10-3", "7")],
)
def test_bare_subtraction_reaches_verified_direct_answer(text, expected):
    assert math_tools.needs_symbolic_math(text)
    intent = math_tools.extract_math_intent(text)
    assert intent is not None and intent.kind == "arithmetic"
    block = math_tools._build_verified_block(intent, Settings(_env_file=None))
    assert block is not None and block.canonical_answer == expected
    reply = maybe_direct_math_reply(block, text)
    assert reply == f"```answer\n{expected}\n```\n"


@pytest.mark.parametrize(
    "text",
    [
        "2026-09-12",
        "2026-09",
        "9/7/2026",
        "9/9",
        "555-1234",
        "555-123-4567",
        "1-800-273-8255",
        "+1-800-273-8255",
        "(555)123-4567",
        "+1 (555) 123-4567",
        "Children ages 2-6",
        "Pick a number in the range 2-6",
        "Open 2-6 pm",
        "The score was 2-6",
        "Call 555-1234",
        "My appointment is 2026-09-12",
    ],
)
def test_dates_phones_and_ranges_in_prose_do_not_become_arithmetic(text):
    assert not math_tools.needs_symbolic_math(text)
    assert math_tools.extract_math_intent(text) is None
