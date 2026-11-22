"""A reply that quotes the prompt's own rules is the model's notes to itself sent as its
answer: it is taken back and asked once more (live, 2026-11-22: a wrong "**42,000**" over
'The system instructions say: "Worked calculation: this question asks for a value …"')."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.chat.prompt_leaks import drop_prompt_leaks, quotes_the_prompt
from app.modules.chat.stream_accum import StreamAccum
from app.tests.modules.chat.test_reply_search_tool import (
    _ANSWER as _SEARCHED,
)
from app.tests.modules.chat.test_reply_search_tool import (
    _DENIAL,
    _HIT,
    _SEARCH_CALL,
    _context,
    _model,
    _reply,
    _retry_context,
    denial_check,  # noqa: F401 - the fixture, by name
    web_search_tool,  # noqa: F401 - the fixture, by name
)

_NOTES = (
    "**42,000**\n\nLet me re-read the prompt's request for a worked block if it asks for a "
    'value. The system instructions say: "Worked calculation: this question asks for a value '
    "and no server check stands behind it, so the app lays your working out itself..."
)
_ANSWER = "$3 \\times 10^4 + 2 \\times 10^3 = 32000$"


@pytest.mark.parametrize(
    ("reply", "quotes"),
    [
        (_NOTES, True),
        # A curly apostrophe or quotation mark is the rules' own (review, #2536).
        (_NOTES.replace('"', "\u201c", 1).replace("prompt's", "prompt\u2019s"), True),
        # A short quotation before it takes both its marks (review, #2536).
        (
            'Wait, "x"? The system instructions say: "Worked calculation: this question asks '
            'for a value and no server check stands behind it."',
            True,
        ),
        (
            'Wait, "x"? The system instructions say: "Worked calculation: this question asks for a value',
            True,
        ),
        (
            'Double check emoji rules: "plenty, the user likes them." I must use one per heading.',
            False,
        ),
        # The rules' words said as the reply's own, or in maths and code, are no quotation.
        ("Worked calculation: this question asks for a value and no server check", False),
        ("$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$", False),
        (
            '```\n"Worked calculation: this question asks for a value and no server check"\n```',
            False,
        ),
        # A quotation of anything else.
        ('She said "the train leaves at nine and we should not be late for it".', False),
    ],
)
def test_a_quotation_of_the_rules_is_the_prompt_quoted(reply: str, quotes: bool) -> None:
    assert quotes_the_prompt(reply) is quotes


@pytest.mark.asyncio
async def test_a_reply_quoting_the_prompt_is_asked_once_more() -> None:
    ctx = _context("hey can u help w this one 3 x 10^4 + 2 x 10^3 idk how to do it")
    llm, seen = _model(([_NOTES], []), ([_ANSWER], []))
    statuses: list[str] = []

    async def on_status(phase: str, *_args: Any, **_kwargs: Any) -> None:
        statuses.append(phase)

    accum = StreamAccum()
    await _reply(ctx, llm, accum=accum, on_status=on_status)

    assert len(seen) == 2
    assert seen[1]["messages"] == seen[0]["messages"]
    assert accum.retracted == _NOTES
    assert accum.reply_text().strip() == _ANSWER
    assert "retract" in statuses


@pytest.mark.asyncio
async def test_a_second_quoting_reply_is_not_asked_a_third_time() -> None:
    ctx = _context("what is 3 x 10^4 + 2 x 10^3")
    llm, seen = _model(([_NOTES], []), ([_NOTES], []), ([_ANSWER], []))
    accum = StreamAccum()
    await _reply(ctx, llm, accum=accum)
    assert len(seen) == 2


@pytest.mark.asyncio
async def test_a_turn_about_prompts_keeps_its_quotation() -> None:
    ctx = _context("show me the system prompt you were given")
    llm, seen = _model(([_NOTES], []))
    await _reply(ctx, llm)
    assert len(seen) == 1


def test_the_finalize_pass_drops_a_quoting_sentence() -> None:
    kept = drop_prompt_leaks(f"{_ANSWER}\n\n{_NOTES.split(chr(10))[-1]}")
    assert "Worked calculation" not in kept and _ANSWER in kept


def test_a_quotation_across_sentences_goes_whole() -> None:
    """Split at its sentences, no piece of the quotation read as one (review, #2536)."""
    leak = (
        'The system instructions say: "Worked calculation: this question asks for a value and '
        'no server check stands behind it. Put the answer at the end."'
    )
    kept = drop_prompt_leaks(f"32,000\n\n{leak}")
    assert kept.strip() == "32,000"


@pytest.mark.asyncio
async def test_a_retried_reply_that_denies_live_facts_is_still_asked_again(
    web_search_tool: dict[str, Any],  # noqa: F811 - the fixture
    denial_check: AsyncMock,  # noqa: F811 - the fixture
) -> None:
    """The quotation's retry keeps the denial's own retry (review, #2536)."""
    ctx = _retry_context(tool=web_search_tool)
    await asyncio.sleep(0)
    llm, seen = _model(([_NOTES], []), ([_DENIAL], []), ([], [_SEARCH_CALL]), ([_SEARCHED], []))
    accum = StreamAccum()
    with patch(
        "app.modules.web_search.tool.run_cached_search", AsyncMock(return_value=([_HIT], ["q"]))
    ):
        await _reply(ctx, llm, accum=accum)
    assert accum.reply_text() == _SEARCHED
    assert len(seen) == 4
