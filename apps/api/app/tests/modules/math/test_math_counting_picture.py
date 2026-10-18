"""Small whole-number facts are drawn as objects to count; big ones keep the written method."""

import json

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.modules.math.schemas.teaching import CountingSpec
from app.modules.math.tools.direct import maybe_direct_math_reply
from app.modules.math.tools.prompt import build_math_augmentation


async def _reply(query: str) -> str:
    _, verified = await build_math_augmentation(query, Settings(math_tools_enabled=True))
    reply = maybe_direct_math_reply(verified, query)
    assert reply is not None
    return reply


def _picture(reply: str) -> dict[str, object] | None:
    if not reply.startswith("```arithmetic\n"):
        return None
    body = reply.split("```arithmetic\n", 1)[1].split("\n```", 1)[0]
    data = json.loads(body)
    return data if data.get("type") == "counting" else None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "operation", "first", "second", "result", "sentence"),
    [
        ("3-3", "subtract", 3, 3, 0, "Take away 3. None are left."),
        ("4-3", "subtract", 4, 3, 1, "1 ball is left."),
        ("3+4", "add", 3, 4, 7, "3 balls and 4 more make 7 balls."),
        ("10+10", "add", 10, 10, 20, "make 20"),
        ("3*4", "multiply", 3, 4, 12, "3 rows of 4"),
        ("12 ÷ 3", "divide", 12, 3, 4, "shared into 3 equal groups is 4 in each group."),
        ("explain 9-4", "subtract", 9, 4, 5, "5 strawberries are left."),
        # The app's own suggestion wording, with the real minus sign it prints.
        ("What if it were 3 \u2212 2?", "subtract", 3, 2, 1, "1 apple is left."),
        ("what if it was 12 \u00f7 3?", "divide", 12, 3, 4, "4 in each group."),
        ("3 \u2212 2", "subtract", 3, 2, 1, "1 apple is left."),
    ],
)
async def test_a_small_fact_is_drawn_as_objects_with_one_sentence(
    query: str, operation: str, first: int, second: int, result: int, sentence: str
) -> None:
    reply = await _reply(query)
    picture = _picture(reply)
    assert picture is not None
    assert (picture["operation"], picture["first"], picture["second"], picture["result"]) == (
        operation,
        first,
        second,
        result,
    )
    assert sentence in reply
    assert "```answer" in reply


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    ["11+2", "123+45", "7*8", "just the answer 3-3"],
)
async def test_big_numbers_and_answer_only_get_no_picture(query: str) -> None:
    assert _picture(await _reply(query)) is None


def test_counting_spec_rejects_a_picture_that_shows_the_wrong_fact() -> None:
    with pytest.raises(ValidationError):
        CountingSpec(
            operation="subtract",
            first=3,
            second=4,
            result=1,
            object="🍎",
            answer="1",
            speech="x",
        )
    with pytest.raises(ValidationError):
        CountingSpec(
            operation="add", first=3, second=4, result=8, object="🍎", answer="8", speech="x"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["3-3", "3*4", "explain 9-4"])
async def test_the_fence_rewriter_keeps_the_verified_picture_only(query: str) -> None:
    from dataclasses import replace

    from app.modules.math.fence import validate_math_fences
    from app.modules.math.response_intent import classify_math_response_intent

    _, verified = await build_math_augmentation(query, Settings(math_tools_enabled=True))
    assert verified is not None
    scoped = replace(verified, response_intent=classify_math_response_intent(query))
    reply = maybe_direct_math_reply(verified, query) or ""
    shown = validate_math_fences(reply, verified=scoped)
    assert '"type":"counting"' in shown
    assert shown.count("```answer") == 1
    tampered = reply.replace('"result":', '"result":1', 1)
    assert '"type":"counting"' not in validate_math_fences(tampered, verified=scoped)


@pytest.mark.parametrize(
    ("text", "is_math"),
    [
        ("What if it were 3 \u2212 2?", True),
        ("what if it were bigger?", False),
        ("What if it rains tomorrow at 3?", False),
    ],
)
def test_a_what_if_sum_is_maths_and_a_what_if_question_is_not(text: str, is_math: bool) -> None:
    from app.modules.math.tools.prompt import needs_symbolic_math

    assert needs_symbolic_math(text) is is_math


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "Show 8 + 7 using carrying",
        "9 - 4 using borrowing",
        "12 ÷ 3 using long division",
        "show 8+7 with column addition",
    ],
)
async def test_a_named_written_method_keeps_its_column_trace(query: str) -> None:
    reply = await _reply(query)
    assert _picture(reply) is None
    assert '"type":"arithmetic"' in reply
