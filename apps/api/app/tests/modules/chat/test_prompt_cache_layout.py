"""The system prompt is ordered for prompt caching, and states each instruction once.

The first system message is the same text on every turn of one kind for one user, so a
provider can reuse it; the clock, memory and files of the turn come after it. A reply
policy or contract that two places add keeps only its copy closest to the user turn.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from app.modules.chat.prompt_builder import inject_web_and_tools
from app.modules.chat.prompt_constants import (
    FACT_GROUNDING_HINT,
    FORMAT_CONTRACT,
    PERSONAL_DISCLOSURE_HINT,
    PHOTO_LOOKUP_HINT,
    STYLE_HINTS,
    UNCLEAR_MESSAGE_HINT,
    learning_plan_daily_contract,
)
from app.modules.chat.prompt_repeats import REPLY_POLICIES, last_copies, policies_once
from app.modules.chat.tool_loop.results import ToolResults
from app.modules.chat.tool_loop.rounds import _hand_off
from app.modules.math.reply_policy import MATH_REPLY_POLICY
from app.modules.physics import PHYSICS_REPLY_POLICY
from app.modules.web_search import WEB_SEARCH_HINT
from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.harness import route_case
from app.tests.modules.chat.chat_test_support import system_prompt
from app.tests.modules.chat.test_prompt_golden import _DEFAULTS, render, resolve

_NINE = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)
_SEVEN_PAST = datetime(2026, 10, 14, 6, 7, tzinfo=UTC)
_QUERY = "what should I cook tonight?"
# A rich turn in a chat with one earlier exchange: memory, schedule and clock all load.
_RICH: dict[str, Any] = {
    "history": [["user", "hi"], ["assistant", "Hey Bini!"], ["user", _QUERY]],
    "kwargs": {"query_text": _QUERY, "rich_context": True, "advice_memory": True, "current": 2},
}


async def _prompt_at(when: datetime, **case: Any) -> list[dict[str, str]]:
    with patch("app.tests.behavior.sweep.SWEEP_NOW", when):
        messages, _out = await render(resolve({**_RICH, **case}, _DEFAULTS))
    return messages


@pytest.mark.asyncio
async def test_the_stable_message_is_byte_identical_at_another_time_with_other_memory() -> None:
    first = await _prompt_at(
        _NINE,
        memory_block="## Preferences\n- Vegetarian.",
        todos_section="Open reminders:\n- Pay rent (due Fri Oct 16)",
    )
    later = await _prompt_at(
        _SEVEN_PAST,
        memory_block="## Preferences\n- Vegetarian.\n- Allergic to peanuts.",
        todos_section="Open reminders:\n- Call the dentist (overdue by 2 days)",
    )
    assert first[0] == later[0]
    # Only the turn's own message differs: its clock, memory and schedule.
    assert first[1] != later[1]
    assert first[2:] == later[2:]
    assert "9:00:00 AM" in first[1]["content"] and "9:07:00 AM" in later[1]["content"]
    for turn_only in ("Current local time", "Digital clock now", "Vegetarian", "Pay rent"):
        assert turn_only not in first[0]["content"]
        assert turn_only in first[1]["content"]


@pytest.mark.asyncio
async def test_fixed_instructions_then_the_users_own_then_the_turns() -> None:
    messages = await _prompt_at(
        _NINE,
        memory_block="## Preferences\n- Vegetarian.",
        todos_section="Open reminders:\n- Pay rent",
        user={"custom_instructions": "Keep it upbeat.", "locale": "es", "job": "Designer"},
        kwargs={**_RICH["kwargs"], "summary": "They planned a trip to Lalibela."},
    )
    stable, turn = messages[0]["content"], messages[1]["content"]
    assert stable.startswith("You are Recall, a helpful personal AI assistant.")
    # The same instructions for every user come before anything about this user.
    users_own = stable.index("User profile")
    for fixed in (
        STYLE_HINTS["balanced"],
        FORMAT_CONTRACT,
        UNCLEAR_MESSAGE_HINT,
        FACT_GROUNDING_HINT,
        WEB_SEARCH_HINT,
        PHOTO_LOOKUP_HINT,
    ):
        assert stable.index(fixed) < users_own
    # Their profile, their own instructions, then their language close the stable message.
    order = ("- Job: Designer", "Keep it upbeat.", "(locale code: es)")
    assert [stable.index(text) for text in order] == sorted(stable.index(t) for t in order)
    assert stable.endswith("do not keep replying in a previous language.")
    # The chat's summary, rewritten every few turns of a long chat, opens the turn's
    # message; the clock, memory and the schedule follow it.
    assert "Lalibela" not in stable
    assert turn.startswith("[BEGIN UNTRUSTED CONTENT — conversation summary]")
    parts = ("Lalibela", "Current local time:", "Digital clock now", "Vegetarian", "Pay rent")
    assert [turn.index(text) for text in parts] == sorted(turn.index(t) for t in parts)
    # The user's latest message stays last.
    assert messages[-1] == {"role": "user", "content": _QUERY}


@pytest.mark.asyncio
async def test_the_disclosure_contract_is_stated_once_closest_to_the_user_turn() -> None:
    query = "I work at Uber as a data analyst"
    messages = await _prompt_at(
        _NINE, history=[["user", query]], kwargs={"query_text": query, "current": 0}
    )
    prompt = system_prompt(messages)
    assert prompt.count(PERSONAL_DISCLOSURE_HINT) == 1
    assert messages[1]["content"].endswith(PERSONAL_DISCLOSURE_HINT)


@pytest.mark.asyncio
async def test_a_plan_contract_is_stated_once_beside_the_user_turn() -> None:
    query = "make me a 7-day plan to learn SQL"
    messages = await _prompt_at(
        _NINE, history=[["user", query]], kwargs={"query_text": query, "current": 0}
    )
    contract = learning_plan_daily_contract(query)
    assert contract
    assert sum(message["content"].count(contract) for message in messages) == 1
    assert messages[-2] == {"role": "system", "content": contract}


def test_last_copies_keeps_a_repeated_part_only_where_it_comes_last() -> None:
    stable, turn, nearby = last_copies(["A", "P", "B", "Q"], ["C", "P"], ["Q", "D"])
    assert (stable, turn, nearby) == (["A", "B"], ["C", "P"], ["Q", "D"])
    assert last_copies(["A", "B"], []) == [["A", "B"], []]


def test_every_subject_reply_policy_is_kept_once() -> None:
    assert set(REPLY_POLICIES) == {MATH_REPLY_POLICY, PHYSICS_REPLY_POLICY}


@pytest.mark.parametrize("policy", [MATH_REPLY_POLICY, PHYSICS_REPLY_POLICY])
def test_a_solve_block_keeps_the_policy_and_the_system_prompt_drops_its_copy(policy: str) -> None:
    stable = f"You are Recall.\n\nFORMAT\n\n{policy}\n\nTone: casual."
    block = (
        f"[BEGIN VERIFIED]\nx = 6\n[END VERIFIED]\n\nReply guidance: data, not a lesson. {policy}"
    )
    prompt = [
        {"role": "system", "content": stable},
        {"role": "system", "content": "Current local time: 9:00 AM"},
        {"role": "system", "content": block},
        {"role": "user", "content": "solve 2x + 5 = 17 and explain"},
    ]
    once = policies_once(prompt)
    assert once[0]["content"] == "You are Recall.\n\nFORMAT\n\nTone: casual."
    assert once[1:] == prompt[1:]
    # The prompt it was given is left as it was.
    assert prompt[0]["content"] == stable


def test_a_policy_left_alone_in_its_message_drops_the_message() -> None:
    prompt = [
        {"role": "system", "content": MATH_REPLY_POLICY},
        {
            "role": "system",
            "content": f"Unverified: no solver result.\n\n{MATH_REPLY_POLICY} Check it.",
        },
        {"role": "user", "content": "x"},
    ]
    assert policies_once(prompt) == prompt[1:]


def test_a_policy_joined_mid_sentence_leaves_the_sentence_whole() -> None:
    note = f"Math note: not verified.\n\n{MATH_REPLY_POLICY} Check it yourself."
    prompt = [
        {"role": "system", "content": note},
        {"role": "system", "content": MATH_REPLY_POLICY},
    ]
    assert policies_once(prompt)[0]["content"] == "Math note: not verified.\n\nCheck it yourself."


@pytest.mark.asyncio
async def test_injecting_a_solve_block_leaves_one_policy_in_the_prompt() -> None:
    prompt = [
        {"role": "system", "content": f"STYLE\n\n{MATH_REPLY_POLICY}"},
        {"role": "system", "content": "Current local time: 9:00 AM"},
        {"role": "user", "content": "solve 2x + 5 = 17 and explain"},
    ]
    block = f"[BEGIN VERIFIED MATH]\nx = 6\n[END VERIFIED MATH]\n\n{MATH_REPLY_POLICY}"
    injected = await inject_web_and_tools(prompt, "WEB RESULTS", block)
    assert [message["content"] for message in injected] == [
        "STYLE",
        "Current local time: 9:00 AM",
        "WEB RESULTS",
        block,
        "solve 2x + 5 = 17 and explain",
    ]
    # Without a solve block nothing is taken out.
    assert await inject_web_and_tools(prompt, "WEB RESULTS", None) == [
        *prompt[:2],
        {"role": "system", "content": "WEB RESULTS"},
        prompt[2],
    ]


def test_a_sympy_round_keeps_the_policy_after_its_results_only() -> None:
    working: list[dict[str, Any]] = [
        {"role": "system", "content": f"STYLE\n\n{MATH_REPLY_POLICY}"},
        {"role": "system", "content": f"BLOCK\n\n{MATH_REPLY_POLICY}"},
        {"role": "user", "content": "integrate x e^x dx and explain"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "1", "function": {"name": "sympy", "arguments": "{}"}}],
        },
        {"role": "tool", "tool_call_id": "1", "content": "x e^x - e^x + C"},
    ]
    outcome = _hand_off(working, 3, ToolResults())
    contents = [message.get("content") for message in outcome.messages]
    assert contents[:2] == ["STYLE", "BLOCK"]
    assert contents[-1] == MATH_REPLY_POLICY
    assert sum(MATH_REPLY_POLICY in (content or "") for content in contents) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt, policy",
    [
        ("solve 2x + 5 = 17 and explain why each step works", MATH_REPLY_POLICY),
        (
            "Two 6 ohm resistors in parallel are in series with a 3 ohm resistor across a "
            "12 V battery. Find the current from the battery.",
            PHYSICS_REPLY_POLICY,
        ),
    ],
)
async def test_a_model_written_stem_turn_states_its_policy_once(prompt: str, policy: str) -> None:
    """Through the real turn path: the subject pack and the solve block both carry it."""
    route = await route_case(Case("policy-once", "stem", prompt, Expect(), ""))
    assert not route.instant
    assert route.system_prompt.count(policy) == 1
