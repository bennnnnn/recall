"""A brief math explanation follows its adjacent exchange without importing stale topics."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.services.chat.prompt_builder import _PromptContextBlocks, build_prompt_messages
from app.services.math_followup import (
    MATH_FOLLOWUP_HINT,
    is_math_followup,
    readable_standalone_answer,
)
from app.services.math_reply_policy import MATH_REPLY_POLICY

_SPEED_ASK = "Find the average speed for 100 m in 20 s."
_SPEED_RESULT = r"5.0\ \mathrm{m}/\mathrm{s}"
_TAYLOR_ASK = "Find the Taylor series of exp(x) at 1 order 2"
_TAYLOR_RESULT = r"\frac{e \left(x - 1\right)^{2}}{2} + e \left(x - 1\right) + e"


def _message(role: str, content: str) -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), role=role, content=content)


def _exchange(question: str = _SPEED_ASK, result: str = _SPEED_RESULT) -> list[SimpleNamespace]:
    return [_message("user", question), _message("assistant", f"```answer\n{result}\n```")]


@pytest.mark.parametrize(
    "query",
    [
        "how",
        "How?",
        "why?",
        "please explain it",
        "can you show the steps?",
        "explain step by step",
        "prove it",
        "show the proof",
        "hint only",
        "give me a hint",
        "give examples",
        "explain with an example",
    ],
)
def test_short_referential_request_uses_immediate_math_exchange(query: str) -> None:
    assert is_math_followup(query, _exchange())


@pytest.mark.parametrize(
    "query",
    [
        "how is the weather?",
        "how do I cook rice?",
        "explain photosynthesis",
        "why is the sky blue?",
        "how, and book a table",
        "how and solve x=2",
        "give me examples of dogs",
        "hi",
        "thanks",
        "",
        None,
        "how " * 40,
    ],
)
def test_unrelated_or_additional_request_does_not_inherit_math(query: str | None) -> None:
    assert not is_math_followup(query, _exchange())


@pytest.mark.parametrize(
    "recent",
    [
        [],
        [_message("assistant", "5")],
        [_message("user", _SPEED_ASK)],
        [
            *_exchange(),
            _message("user", "Tell me about dogs"),
            _message("assistant", "Dogs are mammals."),
        ],
        [*_exchange(), _message("user", "hi"), _message("assistant", "Hello")],
        [*_exchange(), _message("user", "how")],
        [_message("user", _SPEED_ASK), _message("assistant", "")],
        [_message("assistant", "5"), _message("user", _SPEED_ASK)],
    ],
)
def test_no_lookback_through_an_incomplete_or_unrelated_exchange(
    recent: list[SimpleNamespace],
) -> None:
    assert not is_math_followup("how", recent)


@pytest.mark.parametrize(
    "body", [_SPEED_RESULT, _TAYLOR_RESULT, r"x = 2 \pi k,\quad k\in\mathbb{Z}"]
)
def test_standalone_answer_preserves_full_math_without_an_owned_fence(body: str) -> None:
    assert (
        readable_standalone_answer(f"```answer\n{body}\n```\n")
        == f"Previous result:\n\\[\n{body}\n\\]"
    )


@pytest.mark.parametrize(
    "content",
    [
        "```answer\n",
        "```answer\nx=2",
        "```answer\n\n```",
        "````answer\nx=2\n````",
        "```answer extra\nx=2\n```",
        "text\n```answer\nx=2\n```",
        "```answer\nx=2\n```\nextra",
        "```answer\n$x=2$\n```",
        '```answer\n{"type":"geometry","width":3}\n```',
        "```answer\n[1,2]\n```",
        "```answer\nx=2\n```\n```geometry\n{}\n```",
        "```answer\nx=2\n```\n```answer\ny=3\n```",
        "```python\n```answer\nx=2\n```\n```",
        "```geometry\n{}\n```",
        "```answer\n" + "x" * 4001 + "\n```",
    ],
)
def test_incomplete_mixed_or_payload_fences_are_not_retained_as_math(content: str) -> None:
    assert readable_standalone_answer(content) is None


async def _prompt(
    query: str,
    recent: list[SimpleNamespace],
    style: str = "balanced",
    omit_message_ids: set[UUID] | None = None,
    current_user_message_id: UUID | None = None,
) -> list[dict[str, str]]:
    user = User(
        id=uuid4(),
        name="Test",
        email="test@example.com",
        response_style=style,
        locale="en",
        timezone="UTC",
    )
    blocks = _PromptContextBlocks(
        memory_block="",
        todos_section=None,
        gmail_todos_section=None,
        projects_block="",
        recent_all=recent,
        attachment_rag_block="",
        chat=None,
    )
    with patch(
        "app.services.chat.prompt_builder._load_context_blocks", AsyncMock(return_value=blocks)
    ):
        return await build_prompt_messages(
            user,
            uuid4(),
            Settings(attachment_rag_enabled=False),
            query_text=query,
            rich_context=False,
            recent_messages=recent,
            omit_message_ids=omit_message_ids,
            current_user_message_id=current_user_message_id,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question,result", [(_SPEED_ASK, _SPEED_RESULT), (_TAYLOR_ASK, _TAYLOR_RESULT)]
)
@pytest.mark.parametrize("style", ["balanced", "short", "detailed"])
async def test_actual_how_examples_keep_prior_result_and_final_scoped_policy(
    question: str, result: str, style: str
) -> None:
    recent = _exchange(question, result)
    prepared = await _prompt("how", recent, style)
    assert prepared[0]["content"].endswith(f"{MATH_REPLY_POLICY}\n\n{MATH_FOLLOWUP_HINT}")
    assert prepared[-2] == {"role": "user", "content": question}
    assert prepared[-1] == {"role": "assistant", "content": f"Previous result:\n\\[\n{result}\n\\]"}
    assert "unrequested comparisons, unit conversions" in prepared[0]["content"]
    assert "not fresh solver verification" in prepared[0]["content"]
    assert recent[-1].content == f"```answer\n{result}\n```"
    assert all("```answer" not in item["content"] for item in prepared[1:])


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["prove it", "hint only", "give examples"])
async def test_followup_policy_preserves_requested_proof_hint_and_examples(query: str) -> None:
    prepared = await _prompt(query, _exchange())
    policy = prepared[0]["content"]
    assert policy.endswith(MATH_FOLLOWUP_HINT)
    assert "proof, hint, or examples keeps its requested scope" in policy
    assert "a hint must not reveal the solution" in policy


@pytest.mark.asyncio
async def test_previous_nonmath_exchange_does_not_gain_policy_from_older_math() -> None:
    recent = [
        *_exchange(),
        _message("user", "How are clouds made?"),
        _message("assistant", "Water vapor condenses."),
    ]
    prepared = await _prompt("how", recent)
    assert MATH_FOLLOWUP_HINT not in prepared[0]["content"]
    assert MATH_REPLY_POLICY not in prepared[0]["content"]
    assert prepared[2]["content"] == ""
    assert prepared[-1]["content"] == "Water vapor condenses."


@pytest.mark.asyncio
async def test_nonreferential_question_keeps_existing_answer_fence_stripping() -> None:
    prepared = await _prompt("how do I cook rice?", _exchange())
    assert MATH_FOLLOWUP_HINT not in prepared[0]["content"]
    assert prepared[-1]["content"] == ""


@pytest.mark.asyncio
async def test_followup_never_reintroduces_geometry_graph_or_tool_payloads() -> None:
    recent = [
        _message("user", "Find area of a rectangle 3 by 4"),
        _message(
            "assistant", 'Area is 12.\n```geometry\n{"width":3}\n```\n```graph\n{"points":[]}\n```'
        ),
    ]
    prepared = await _prompt("how", recent)
    assert prepared[0]["content"].endswith(MATH_FOLLOWUP_HINT)
    assert prepared[-1]["content"].strip() == "Area is 12."
    assert "width" not in prepared[-1]["content"]
    assert "points" not in prepared[-1]["content"]


@pytest.mark.asyncio
async def test_regenerated_how_keeps_prior_result_and_persisted_current_user() -> None:
    recent = [*_exchange(), _message("user", "how"), _message("assistant", "Old explanation")]
    prepared = await _prompt("how", recent, omit_message_ids={recent[-1].id})
    assert prepared[0]["content"].endswith(MATH_FOLLOWUP_HINT)
    assert prepared[-2] == {
        "role": "assistant",
        "content": f"Previous result:\n\\[\n{_SPEED_RESULT}\n\\]",
    }
    assert prepared[-1] == {"role": "user", "content": "how"}
    assert all("Old explanation" not in item["content"] for item in prepared)


@pytest.mark.asyncio
async def test_unrelated_omission_does_not_strip_an_incomplete_current_user() -> None:
    older = _message("assistant", "Older answer")
    recent = [older, *_exchange(), _message("user", "how")]
    prepared = await _prompt("how", recent, omit_message_ids={older.id})
    assert MATH_FOLLOWUP_HINT not in prepared[0]["content"]
    assert prepared[-2]["content"] == ""
    assert prepared[-1] == {"role": "user", "content": "how"}


@pytest.mark.asyncio
async def test_explicit_current_user_id_keeps_the_previous_completed_math_exchange() -> None:
    recent = [*_exchange(), _message("user", "how")]
    prepared = await _prompt("how", recent, current_user_message_id=recent[-1].id)
    assert prepared[0]["content"].endswith(MATH_FOLLOWUP_HINT)
    assert prepared[-2]["content"] == f"Previous result:\n\\[\n{_SPEED_RESULT}\n\\]"
    assert prepared[-1] == {"role": "user", "content": "how"}


@pytest.mark.asyncio
@pytest.mark.parametrize("identity", ["missing", "different", "earlier"])
async def test_matching_query_without_current_turn_identity_is_not_sufficient(
    identity: str,
) -> None:
    recent = [*_exchange(), _message("user", "how")]
    message_id = (
        None if identity == "missing" else (uuid4() if identity == "different" else recent[0].id)
    )
    prepared = await _prompt("how", recent, current_user_message_id=message_id)
    assert MATH_FOLLOWUP_HINT not in prepared[0]["content"]
    assert prepared[-2]["content"] == ""


@pytest.mark.asyncio
async def test_current_turn_id_with_changed_content_does_not_hijack_previous_math() -> None:
    recent = [*_exchange(), _message("user", "how do I cook rice?")]
    prepared = await _prompt("how", recent, current_user_message_id=recent[-1].id)
    assert MATH_FOLLOWUP_HINT not in prepared[0]["content"]
