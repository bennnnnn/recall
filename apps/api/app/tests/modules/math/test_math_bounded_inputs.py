"""A number past a solver's bounds is a decline, never an error.

"100000!" read as a factorial of 100000, and the combinatorics input (n at most 1000)
refused it with a ValidationError that was logged as "math_tools failed" with its
traceback: Sentry noise on every such message (audit REL-05, 2026-11-13).
"""

import logging

import pytest

from app.core.config import Settings
from app.modules.math.tools.block import _build_verified_block
from app.modules.math.tools.extract import extract_math_intent

_SETTINGS = Settings(math_tools_enabled=True)


@pytest.mark.parametrize(
    "query",
    [
        "100000!",
        "What is 100000!?",
        "1001!",
        "5000 choose 3",
        "P(2000, 2)",
        "factorize 1000000000000",
        "is 123456789012 prime",
    ],
)
def test_math_input_past_its_bounds_declines_quietly(
    query: str, caplog: pytest.LogCaptureFixture
) -> None:
    intent = extract_math_intent(query)
    assert intent is not None
    with caplog.at_level(logging.INFO, logger="app.modules.math.tools.block"):
        assert _build_verified_block(intent, _SETTINGS) is None
    assert [record.levelno for record in caplog.records] == [logging.INFO]
    assert caplog.records[0].exc_info is None
    # The class only: the error's message would quote the number the user typed.
    assert caplog.records[0].getMessage() == "math_tools skipped: ValidationError"


@pytest.mark.parametrize("query,answer", [("5!", "120"), ("10 choose 3", "120")])
def test_math_input_within_its_bounds_is_still_solved(query: str, answer: str) -> None:
    intent = extract_math_intent(query)
    assert intent is not None
    block = _build_verified_block(intent, _SETTINGS)
    assert block is not None and answer in (block.canonical_answer or "")
