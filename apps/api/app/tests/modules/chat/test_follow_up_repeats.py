"""Follow-up questions are new to the chat and fit the question asked (2026-10-24).

One study chat showed "Why use Kelvin not Celsius?" under four replies after the user
had asked it, offered "What if it was $-2x + 5 = 0$?" beside "How does it change for
$-2x + 5 = 0$?", and answered "who was Charles from Charles's law?" with "What if the
temperature doubles?".
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.account.lifecycle import purge_user_redis_keys
from app.modules.chat import related_prompts
from app.modules.chat.follow_up_repeats import repeats_earlier
from app.modules.chat.related_prompts import (
    RelatedQuestions,
    generate_related_questions,
    schedule_related_prompts,
    shown_in_chat,
)
from app.modules.chat.related_questions import accepted_questions, follow_up_topic

_ASKED = "Why is temperature in Kelvin for Charles's law?"
_BLOCK = (
    "A 2 kg block slides down a frictionless incline of angle 30 degrees. "
    "Find its acceleration and the normal force."
)
_REPLY = "Charles's law ties volume to absolute temperature, so it needs kelvin. " * 6


@pytest.mark.parametrize(
    ("candidate", "earlier"),
    [
        ("Why use Kelvin not Celsius?", ["Why use Kelvin not Celsius?"]),
        ("Why use Kelvin instead of Celsius?", ["Why use Kelvin not Celsius?"]),
        ("Why use Kelvin for Charles's Law?", [_ASKED]),
        ("How does it change for $-2x + 5 = 0$?", ["What if it was $-2x+5=0$?"]),
        ("Why do mole ratios matter?", ["How do mole ratios work?"]),
    ],
)
def test_a_reworded_question_repeats_the_earlier_one(candidate: str, earlier: list[str]) -> None:
    assert repeats_earlier(candidate, earlier)


@pytest.mark.parametrize(
    ("candidate", "earlier"),
    [
        ("What if pressure halves?", ["What if pressure doubles?"]),
        ("What if $3x + 3 = 7$?", ["What if $3x + 3 = 5$?"]),
        ("How does pressure affect volume?", ["What if pressure doubles and volume halves?"]),
        ("Why use Kelvin?", ["Why use Kelvin not Celsius?"]),  # one topic word decides nothing
        ("Who discovered Boyle's law?", [_ASKED, ""]),
        # A name in maths is no equation; a longer question on a shared topic is new.
        ("What if $x$ were negative?", ["Why isolate $x$ first?"]),
        (
            "What is the boiling point of water?",
            ["Why does water's boiling point drop at altitude?"],
        ),
        # A what-if on one quantity of a problem statement is the point of a follow-up.
        ("What if the angle is 45 degrees?", [_BLOCK]),
        ("How does the normal force change with angle?", [_BLOCK]),
    ],
)
def test_a_new_question_is_not_a_repeat(candidate: str, earlier: list[str]) -> None:
    assert not repeats_earlier(candidate, earlier)


def test_a_set_keeps_one_of_two_alike_and_none_asked_before() -> None:
    kept = accepted_questions(
        "wait the answer is negative, is that allowed?",
        [
            "What if it was $-2x + 5 = 0$?",
            "How does it change for $-2x + 5 = 0$?",
            "Why use Kelvin not Celsius?",
            "Can a negative answer check out in the equation?",
        ],
        problem="solve 2x + 5 = 0",
        anchors=set(),
        earlier=["Why use Kelvin not Celsius?"],
    )
    assert kept == [
        "What if it was $-2x + 5 = 0$?",
        "Can a negative answer check out in the equation?",
    ]


@pytest.mark.parametrize(
    ("question", "topic"),
    [
        ("who was charles from charles's law anyway?", ("general", None)),
        (_ASKED, ("general", None)),
        ("What is photosynthesis?", ("general", None)),
        # Something to vary, or a task rather than a question: the problem's why, what-if
        # and next step, as before.
        ("What is the derivative of sin x?", ("subject", None)),
        ("what is the force on a 10 kg object accelerating at 3 m/s^2", ("subject", None)),
        ("Calculate the molar mass of glucose", ("subject", None)),
        ("I don't understand Charles's law", ("subject", None)),
    ],
)
def test_a_question_with_nothing_to_change_gets_the_topics_next_questions(
    question: str, topic: tuple[str, str | None] | None
) -> None:
    got = follow_up_topic(question, _REPLY, [], allow_general=True)
    if topic is not None and topic[0] == "subject" and topic[1] is None:
        topic = ("subject", question)
    assert got == topic


def test_a_tapped_why_keeps_its_what_ifs() -> None:
    kept = accepted_questions(
        "Why does the normal force get smaller?",
        [
            "What if the angle is 45 degrees?",
            "What is the acceleration at 60 degrees?",
            "How does the normal force change with angle?",
        ],
        problem=_BLOCK,
        earlier=["Why does the normal force get smaller?"],
    )
    assert len(kept) == 3


def test_a_line_after_a_numberless_question_is_judged_as_any_question() -> None:
    prior = [
        {"role": "user", "content": "who was charles from charles's law anyway?"},
        {"role": "assistant", "content": "Jacques Charles was a French physicist."},
    ]
    assert (
        follow_up_topic("do you have a picture of him?", "Here he is.", prior, allow_general=True)
        is None
    )


async def test_the_model_reads_what_the_chat_asked_and_was_shown() -> None:
    prior = [
        {"role": "user", "content": _ASKED},
        {"role": "assistant", "content": "Because volume tracks absolute temperature."},
    ]
    with patch.object(related_prompts, "complete_structured", new_callable=AsyncMock) as complete:
        complete.return_value = RelatedQuestions(
            questions=[
                "Why use Kelvin for Charles's Law?",
                "Who was Jacques Charles?",
                "What did Gay-Lussac add to Charles's work?",
                "How was absolute zero first estimated?",
            ]
        )
        prompts = await generate_related_questions(
            Settings(),
            "who was charles from charles's law anyway?",
            _REPLY,
            prior,
            shown=["Why use Kelvin not Celsius?"],
        )
    call = complete.await_args
    assert call is not None
    sent = call.kwargs["messages"][1]["content"]
    assert "Already asked or suggested in this chat" in sent
    assert f"- {_ASKED}" in sent and "- Why use Kelvin not Celsius?" in sent
    assert prompts == [
        "Who was Jacques Charles?",
        "What did Gay-Lussac add to Charles's work?",
        "How was absolute zero first estimated?",
    ]


async def test_shown_questions_are_kept_per_chat_for_the_next_set(fake_redis) -> None:
    first = [
        "Who was Jacques Charles?",
        "What did Gay-Lussac add to Charles's work?",
        "How was absolute zero first estimated?",
    ]
    with patch.object(related_prompts, "complete_structured", new_callable=AsyncMock) as complete:
        complete.return_value = RelatedQuestions(questions=first)
        task = schedule_related_prompts(
            fake_redis,
            Settings(),
            message_id="m1",
            question="who was charles from charles's law anyway?",
            answer=_REPLY,
            chat=("u1", "c1"),
        )
        assert task is not None
        await task
    assert await shown_in_chat(fake_redis, "u1", "c1") == first
    assert await shown_in_chat(fake_redis, "u1", "c2") == []
    stored = await fake_redis.get("related_prompts:shown:u1:c1")
    assert json.loads(stored) == first


async def test_the_account_purge_drops_what_a_chat_was_shown(fake_redis) -> None:
    user_id = uuid4()
    await fake_redis.set(f"related_prompts:shown:{user_id}:{uuid4()}", json.dumps(["q?"]))
    assert await purge_user_redis_keys(fake_redis, user_id) == 1
