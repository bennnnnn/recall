"""Follow-up questions come from the model, after done, and survive a reopen."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.chat.related_prompts import (
    RelatedQuestions,
    _digit_skeleton,
    generate_related_questions,
    load_related_prompts,
    schedule_related_prompts,
    store_related_prompts,
    subject_for_related,
    thread_problem,
)
from app.modules.chat.service import list_messages_page
from app.modules.chat.stream_events import build_done_payload, take_related_prompts_event

PHYSICS = "what is the force on a 10 kg object accelerating at 3 m/s^2"
PHYSICS_FOLLOWUPS = [
    "Why is the force the product of mass and acceleration?",
    "What changes if this object is already moving?",
    "How do you find the acceleration from the force and the mass?",
]
PHOTO = "What is photosynthesis?"
PHOTO_FOLLOWUPS = [
    "Why does photosynthesis need light?",
    "What happens to the sugar a plant makes?",
    "How is cellular respiration tied to this process?",
]


@pytest.mark.parametrize(
    ("question", "answer", "followups"),
    [
        (PHYSICS, "The force is 30 newtons.", PHYSICS_FOLLOWUPS),
        (PHOTO, "Plants make sugar from light.", PHOTO_FOLLOWUPS),
    ],
)
async def test_subject_question_returns_the_models_questions(
    question: str,
    answer: str,
    followups: list[str],
) -> None:
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(questions=followups)
        prompts = await generate_related_questions(Settings(), question, answer)

    assert prompts == followups
    for prompt in prompts:
        assert _digit_skeleton(prompt) != _digit_skeleton(question)
        assert prompt != question
    call = complete.await_args
    assert call is not None
    sent = " ".join(item["content"] for item in call.kwargs["messages"])
    assert "suggestion" not in sent.casefold()
    assert call.kwargs["model_alias"] == "memory-model"
    assert call.kwargs["allow_fallback"] is False


async def test_a_fragment_or_a_glued_equation_is_dropped() -> None:
    spaced = "Why does a force of $x=5$ give a different value?"
    glued_radical = r"Why does $^5\sqrt{x} = 0^5$ equal zero?"
    glued_variable = "What is the value of $x5$ here?"
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(questions=[spaced, glued_radical, "How"])
        prompts = await generate_related_questions(Settings(), PHYSICS, "The force is 30 newtons.")
        assert prompts == ["Why does a force of $x = 5$ give a different value?"]

        complete.return_value = RelatedQuestions(
            questions=[glued_variable, PHYSICS_FOLLOWUPS[0], PHYSICS_FOLLOWUPS[1]]
        )
        prompts = await generate_related_questions(Settings(), PHYSICS, "The force is 30 newtons.")

    assert glued_variable not in prompts
    assert prompts == PHYSICS_FOLLOWUPS[:2]


async def test_a_digit_change_of_the_same_sentence_is_dropped() -> None:
    tweaked = "what is the force on a 11 kg object accelerating at 3 m/s^2"
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(
            questions=[tweaked, PHYSICS_FOLLOWUPS[0], PHYSICS_FOLLOWUPS[1]]
        )
        prompts = await generate_related_questions(Settings(), PHYSICS, "The force is 30 newtons.")

    assert tweaked not in prompts
    assert prompts == PHYSICS_FOLLOWUPS[:2]


async def test_a_sum_follow_up_that_drops_both_numbers_is_rejected() -> None:
    drifted = (
        "Why does adding two positive numbers always result in a larger number "
        "than either of the original numbers?"
    )
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(questions=[drifted, "What is 3 + 5?"])
        prompts = await generate_related_questions(Settings(), "3+4", "3 + 4 = 7")

    assert drifted not in prompts
    assert prompts == ["What is 3 + 5?"]


def test_an_arithmetic_follow_up_still_asks_for_more() -> None:
    question = "How would you calculate 1 + 1 + 1 + 1?"
    assert subject_for_related(question) == "math"


@pytest.mark.parametrize("text", ["how's your day", "hi"])
async def test_chitchat_does_not_call_the_model(text: str, fake_redis) -> None:
    result: dict[str, Any] = {}
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        schedule_related_prompts(
            result,
            fake_redis,
            Settings(),
            message_id="m1",
            question=text,
            answer="Pretty good.",
        )
        prompts = await generate_related_questions(Settings(), text, "Pretty good.")

    assert "_related_task" not in result
    assert prompts == []
    complete.assert_not_called()


async def test_done_payload_does_not_wait_for_the_follow_up() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    question = PHYSICS_FOLLOWUPS[0]

    async def slow() -> dict[str, object]:
        started.set()
        await release.wait()
        return {"type": "related_prompts", "message_id": "msg-1", "prompts": [question]}

    result: dict[str, Any] = {
        "message_id": "msg-1",
        "_related_task": asyncio.create_task(slow()),
    }
    done = build_done_payload(result)
    assert done["type"] == "done"
    assert "related_prompts" not in done
    assert "prompts" not in done

    waiter = asyncio.create_task(take_related_prompts_event(result.pop("_related_task")))
    await asyncio.wait_for(started.wait(), timeout=1)
    assert not waiter.done()
    release.set()
    event = await waiter
    assert event is not None
    assert event["prompts"] == [question]


async def test_schedule_caches_questions_for_reopen(fake_redis) -> None:
    result: dict[str, Any] = {}
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(questions=PHYSICS_FOLLOWUPS)
        schedule_related_prompts(
            result,
            fake_redis,
            Settings(),
            message_id="abc",
            question=PHYSICS,
            answer="The force is 30 newtons.",
        )
        event = await take_related_prompts_event(result.pop("_related_task"))

    assert event is not None
    assert event["prompts"] == PHYSICS_FOLLOWUPS
    assert await load_related_prompts(fake_redis, "abc") == PHYSICS_FOLLOWUPS
    assert await load_related_prompts(fake_redis, "missing") == []


def _page_rows(assistant_id):
    now = datetime.now(UTC)
    return [
        SimpleNamespace(
            id=uuid4(),
            role="user",
            content=PHYSICS,
            model=None,
            created_at=now,
        ),
        SimpleNamespace(
            id=assistant_id,
            role="assistant",
            content="The force is 30 newtons.",
            model="free-chat",
            created_at=now,
        ),
    ]


async def test_reopen_reads_the_cache_and_does_not_call_the_model(fake_redis) -> None:
    assistant_id = uuid4()
    await store_related_prompts(fake_redis, str(assistant_id), PHYSICS_FOLLOWUPS)
    with (
        patch(
            "app.modules.chat.service.get_chat",
            AsyncMock(return_value=SimpleNamespace(title="Force")),
        ),
        patch("app.modules.chat.service.finalize_registry.wait_for_inflight_stream", AsyncMock()),
        patch("app.modules.chat.service.finalize_registry.wait_for_pending_finalize", AsyncMock()),
        patch(
            "app.modules.chat.service.messages_repo.list_page",
            AsyncMock(return_value=(_page_rows(assistant_id), False)),
        ),
        patch(
            "app.modules.chat.related_prompts.complete_structured",
            new_callable=AsyncMock,
        ) as complete,
    ):
        user = cast(User, SimpleNamespace(id=uuid4()))
        page = await list_messages_page(AsyncMock(), fake_redis, user, uuid4())
        older = await list_messages_page(
            AsyncMock(),
            fake_redis,
            user,
            uuid4(),
            before=uuid4(),
        )

    assert page.messages[-1].related_prompts == PHYSICS_FOLLOWUPS
    assert older.messages[-1].related_prompts is None
    complete.assert_not_called()


BIKE = "A bike travels 45 km in 3 hours. What's its average speed?"
BIKE_WINDOW = [
    {"role": "system", "content": "You are Recall."},
    {"role": "user", "content": BIKE},
    {"role": "assistant", "content": "v = 45 km / 3 h = 15 km/h"},
]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Why do we divide distance by time to get speed?", BIKE),
        ("How do you convert 15 km/h into m/s?", BIKE),
        ("One more", BIKE),
        ("explain the units", BIKE),
        ("thanks", None),
        ("hi", None),
    ],
)
def test_thread_problem_ties_a_follow_up_to_its_problem(line: str, expected: str | None) -> None:
    assert thread_problem(line, BIKE_WINDOW) == expected
    assert thread_problem(line, None) is None


def test_thread_problem_forgets_a_stale_problem() -> None:
    window = [
        *BIKE_WINDOW,
        {"role": "user", "content": "Write a poem about autumn"},
        {"role": "assistant", "content": "Leaves fall."},
        {"role": "user", "content": "Make it rhyme"},
        {"role": "assistant", "content": "Leaves fall all."},
        {"role": "user", "content": "Make it longer"},
        {"role": "assistant", "content": "Leaves fall all day."},
    ]
    assert thread_problem("Why is that?", window) is None


async def test_a_tapped_why_keeps_the_follow_ups_coming() -> None:
    why = "Why do we divide distance by time to get speed?"
    followups = [
        "Why is average speed not the mean of two speeds?",
        "A car travels 120 km in 2 hours. What is its average speed?",
        "How would the average speed change if the bike stopped for 30 minutes?",
    ]
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        # The original problem asked again is dropped.
        complete.return_value = RelatedQuestions(questions=[followups[0], BIKE, followups[2]])
        prompts = await generate_related_questions(
            Settings(), why, "Speed is distance per unit time.", BIKE_WINDOW
        )

    assert prompts == [followups[0], followups[2]]
    sent = complete.call_args.kwargs["messages"][1]["content"]
    assert sent.startswith(f"Problem:\n{BIKE}")
    assert f"Student question:\n{why}" in sent
