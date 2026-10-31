"""A leaked end-of-turn token is no reply text, and a run of them ends the stream
(2026-10-30: a Grade 10 answer card ended "<|im_end|>" and 1,100 lines of "</|im_end|>")."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.modules.chat.control_tokens import strip_control_tokens, until_control_run


def test_a_leaked_token_and_its_run_leave_the_reply() -> None:
    reply = (
        "**Answer**\n\n```answer\n$t = 2 \\times 10^{-8}\\ \\text{s}$<|im_end|>\n```\n\n"
        + "</|im_end|> \n" * 40
    )
    assert strip_control_tokens(reply) == (
        "**Answer**\n\n```answer\n$t = 2 \\times 10^{-8}\\ \\text{s}$\n```\n"
    )


@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        ("The answer is 4.<|endoftext|>", "The answer is 4."),
        ("Done.<|eot_id|>", "Done."),
        ("Done.<\uff5cend\u2581of\u2581sentence\uff5c>", "Done."),
        (
            "Part (a) is 3 A.<|im_end|>\n\n\n\n\nPart (b) is 6 V.",
            "Part (a) is 3 A.\n\nPart (b) is 6 V.",
        ),
    ],
)
def test_each_token_form_goes(reply: str, kept: str) -> None:
    assert strip_control_tokens(reply) == kept


@pytest.mark.parametrize(
    "reply",
    [
        # Someone asking about the tokens gets them quoted as code.
        "In ChatML each turn ends with `<|im_end|>`.\n",
        '```python\nprint("<|im_end|>")\n```\n',
        # Not a token: a vertical bar beside angle brackets in prose or a table.
        "a <| b |> c and x|>y",
        "| a | b |\n|---|---|\n| <1 | >2 |\n",
    ],
)
def test_quoted_code_and_look_alikes_stay(reply: str) -> None:
    assert strip_control_tokens(reply) == reply


async def _stream(tokens: list[str]) -> AsyncIterator[str]:
    for token in tokens:
        yield token


async def test_a_run_of_tokens_ends_the_stream() -> None:
    tokens = ["The time is ", "2e-8 s.", "<|im_end|>", "\n</|", "im_end|> \n", "</|im_end|>"]
    tokens += ["more junk"] * 100
    seen = [token async for token in until_control_run(_stream(tokens))]
    assert seen == tokens[:5]


async def test_one_token_does_not_end_the_stream() -> None:
    tokens = ["See `<|im_end|>`", " for the end of a turn.", " It is a token."]
    seen = [token async for token in until_control_run(_stream(tokens))]
    assert seen == tokens
