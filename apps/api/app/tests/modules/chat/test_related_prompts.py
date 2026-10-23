"""Follow-up questions come from the model, after done, and survive a reopen."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.orm import User
from app.modules.chat.related_prompts import (
    RelatedQuestions,
    generate_related_questions,
    load_related_prompts,
    schedule_related_prompts,
    store_related_prompts,
)
from app.modules.chat.related_questions import _digit_skeleton, subject_for_related, thread_problem
from app.modules.chat.service import list_messages_page
from app.modules.chat.stream_accum import Completion
from app.modules.chat.stream_events import DoneEvent, take_related_prompts_event
from app.modules.chat.turn_outcome import TurnOutcome

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
        complete.return_value = RelatedQuestions(
            questions=[spaced, glued_radical, "How", *PHYSICS_FOLLOWUPS[:2]]
        )
        prompts = await generate_related_questions(Settings(), PHYSICS, "The force is 30 newtons.")
        assert prompts == [
            "Why does a force of $x = 5$ give a different value?",
            *PHYSICS_FOLLOWUPS[:2],
        ]

        complete.return_value = RelatedQuestions(questions=[glued_variable, *PHYSICS_FOLLOWUPS])
        prompts = await generate_related_questions(Settings(), PHYSICS, "The force is 30 newtons.")

    assert glued_variable not in prompts
    assert prompts == PHYSICS_FOLLOWUPS


async def test_a_digit_change_of_the_same_sentence_is_dropped() -> None:
    tweaked = "what is the force on a 11 kg object accelerating at 3 m/s^2"
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(questions=[tweaked, *PHYSICS_FOLLOWUPS])
        prompts = await generate_related_questions(Settings(), PHYSICS, "The force is 30 newtons.")

    assert tweaked not in prompts
    assert prompts == PHYSICS_FOLLOWUPS


async def test_a_sum_follow_up_that_drops_both_numbers_is_rejected() -> None:
    drifted = (
        "Why does adding two positive numbers always result in a larger number "
        "than either of the original numbers?"
    )
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        kept = ["What is 3 + 5?", "Why does 3 + 4 equal 7?", "How can 4 + 3 also make 7?"]
        complete.return_value = RelatedQuestions(questions=[drifted, *kept])
        prompts = await generate_related_questions(Settings(), "3+4", "3 + 4 = 7")

    assert drifted not in prompts
    assert prompts == kept


def test_an_arithmetic_follow_up_still_asks_for_more() -> None:
    question = "How would you calculate 1 + 1 + 1 + 1?"
    assert subject_for_related(question) == "math"


@pytest.mark.parametrize("text", ["how's your day", "hi"])
async def test_chitchat_does_not_call_the_model(text: str, fake_redis) -> None:
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        task = schedule_related_prompts(
            fake_redis,
            Settings(),
            message_id="m1",
            question=text,
            answer="Pretty good.",
        )
        prompts = await generate_related_questions(Settings(), text, "Pretty good.")

    assert task is None
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

    outcome = TurnOutcome(message_id="msg-1", related_task=asyncio.create_task(slow()))
    done = DoneEvent.from_outcome(outcome).model_dump()
    assert done["type"] == "done"
    assert "related_prompts" not in done
    assert "prompts" not in done

    waiter = asyncio.create_task(take_related_prompts_event(outcome.related_task))
    await asyncio.wait_for(started.wait(), timeout=1)
    assert not waiter.done()
    release.set()
    event = await waiter
    assert event is not None
    assert event["prompts"] == [question]


async def test_schedule_caches_questions_for_reopen(fake_redis) -> None:
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(questions=PHYSICS_FOLLOWUPS)
        task = schedule_related_prompts(
            fake_redis,
            Settings(),
            message_id="abc",
            question=PHYSICS,
            answer="The force is 30 newtons.",
        )
        event = await take_related_prompts_event(task)

    assert event is not None
    assert event["prompts"] == PHYSICS_FOLLOWUPS
    assert await load_related_prompts(fake_redis, "abc") == PHYSICS_FOLLOWUPS
    assert await load_related_prompts(fake_redis, "missing") == []


@pytest.mark.parametrize(
    "spent_usd, cap_usd, asks",
    [(0.5, 1.0, True), (1.0, 1.0, False), (3.0, 1.0, False), (3.0, 0.0, True)],
)
async def test_follow_ups_stop_at_the_global_spend_cap(
    fake_redis, spent_usd: float, cap_usd: float, asks: bool
) -> None:
    from app.services.quota import record_global_spend

    await record_global_spend(fake_redis, spent_usd)
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(questions=PHYSICS_FOLLOWUPS)
        task = schedule_related_prompts(
            fake_redis,
            Settings(daily_global_spend_usd=cap_usd),
            message_id="abc",
            question=PHYSICS,
            answer="The force is 30 newtons.",
        )
        event = await take_related_prompts_event(task)

    assert (event is not None) is asks
    assert complete.await_count == int(asks)


@pytest.mark.parametrize("completion", ["user_stop", "interrupted"])
async def test_a_stopped_or_cut_off_reply_gets_no_follow_ups(
    completion: Completion, fake_redis
) -> None:
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        task = schedule_related_prompts(
            fake_redis,
            Settings(),
            message_id="abc",
            question=PHYSICS,
            answer="The force is 30 newtons.",
            completion=completion,
        )

    assert task is None
    complete.assert_not_called()


COUNTRY = "What is the best country to live in?"
COUNTRY_ASKS = (
    "🇨🇭 **Switzerland — best for quality of life**: high wages, safety and healthcare.\n"
    "🇸🇬 **Singapore — best for making money**: low taxes and a strong job market.\n"
    "🇳🇴 **Norway — best for social support**: free education and generous welfare.\n\n"
    "**But let me ask you one thing.**\n\nWhat do you mean by *best*?\n\n```clarify\n"
    '{"request":"Recommend the best country for me.","questions":[{"id":"priority",'
    '"label":"Main priority","question":"What matters most to you?","options":'
    '["💰 Making money","🌿 Quality of life","🛡️ Safety"]},{"id":"region","label":"Region",'
    '"question":"Which region are you considering?","options":["🌍 Anywhere","🇪🇺 Europe",'
    '"🌎 The Americas"]}],"closing":"Compare the strongest options with practical pros and '
    'cons.","submit":"Find my best country"}\n```'
)


def test_a_reply_that_asks_with_the_new_card_gets_no_follow_ups() -> None:
    # The card waits for the picks; questions under it would compete with it.
    from app.modules.chat.related_questions import follow_up_topic

    assert follow_up_topic(COUNTRY, COUNTRY_ASKS, None, allow_general=True) is None


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
        "What if the bike stopped for 30 minutes?",
        "How long would 90 km take at that speed?",
    ]
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        # The original problem asked again is dropped.
        complete.return_value = RelatedQuestions(
            questions=[followups[0], BIKE, followups[2], followups[3]]
        )
        prompts = await generate_related_questions(
            Settings(), why, "Speed is distance per unit time.", BIKE_WINDOW
        )

    assert prompts == [followups[0], followups[2], followups[3]]
    sent = complete.call_args.kwargs["messages"][1]["content"]
    assert sent.startswith(f"Problem:\n{BIKE}")
    assert f"Student question:\n{why}" in sent


AVERAGE = "A car goes from rest to 75 km/h in 5 s. What is its average acceleration?"


async def test_a_follow_up_is_one_short_line() -> None:
    restated = "A car goes from rest to 90 km/h in 6 s. What is its average acceleration?"
    too_long = "How would the acceleration change if the car took twice as long to reach 75 km/h?"
    short = [
        "Why convert km/h to m/s first?",
        "What if it took 10 s instead?",
        "How far does the car go in 5 s?",
    ]
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(questions=[restated, too_long, *short])
        prompts = await generate_related_questions(Settings(), AVERAGE, "a = 4.17 m/s^2")

    assert prompts == short


def test_math_counts_as_what_the_phone_shows() -> None:
    from app.modules.chat.related_questions import _prepare_question

    fraction = r"Why is $\frac{v - v_0}{t}$ the average acceleration here?"
    assert _prepare_question(fraction) == fraction
    assert _prepare_question("Why is 2.5 m/s the speed here?") is not None


SOURDOUGH = "How do I make a sourdough starter at home?"
SOURDOUGH_REPLY = (
    "Mix 50 g of flour with 50 g of water in a clean jar, cover it loosely and keep it "
    "somewhere warm. Every day, discard half and feed it another 50 g of flour and 50 g "
    "of water. After five to seven days it should double within a few hours of feeding, "
    "smell pleasantly sour and be full of bubbles. That is when it is ready to bake with. "
    "Whole wheat or rye flour gets it going faster than white flour."
)


async def test_an_everyday_question_gets_follow_ups_on_its_topic() -> None:
    followups = [
        "How do I know it's ready?",
        "Can I use whole wheat flour?",
        "What is the capital of France?",
        "Why does my starter smell like acetone?",
    ]
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(questions=followups)
        prompts = await generate_related_questions(Settings(), SOURDOUGH, SOURDOUGH_REPLY)

    # The capital of France left the topic.
    assert prompts == [followups[0], followups[1], followups[3]]
    call = complete.await_args
    assert call is not None
    system, user = call.kwargs["messages"]
    assert "about exactly what they just asked" in system["content"]
    assert user["content"].startswith(f"Question:\n{SOURDOUGH}")


@pytest.mark.parametrize(
    "question",
    [
        "Write an email to my landlord about the leaking sink",
        "Remind me to feed the starter tomorrow at 9",
        "I just started baking sourdough bread",
        "Set my reply style to short",
        "thanks so much",
        "Turn on the dark theme for me please",
    ],
)
async def test_drafts_reminders_updates_and_small_talk_get_no_follow_ups(
    question: str, fake_redis
) -> None:
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        task = schedule_related_prompts(
            fake_redis,
            Settings(),
            message_id="m1",
            question=question,
            answer=SOURDOUGH_REPLY,
        )
        prompts = await generate_related_questions(Settings(), question, SOURDOUGH_REPLY)

    assert task is None
    assert prompts == []
    complete.assert_not_called()


async def test_a_short_reply_or_a_greeting_turn_gets_no_everyday_follow_ups(fake_redis) -> None:
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        short = await generate_related_questions(Settings(), SOURDOUGH, "Flour and water.")
        small_talk = await generate_related_questions(
            Settings(), "how's your day going?", "Pretty good, thanks for asking! How about you?"
        )
        off = await generate_related_questions(
            Settings(), SOURDOUGH, SOURDOUGH_REPLY, allow_general=False
        )
        task = schedule_related_prompts(
            fake_redis,
            Settings(),
            message_id="m2",
            question=SOURDOUGH,
            answer=SOURDOUGH_REPLY,
            allow_general=False,
        )

    assert short == []
    assert small_talk == []
    assert off == []
    assert task is None
    complete.assert_not_called()


async def test_a_subject_problem_ignores_the_everyday_switch() -> None:
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(questions=PHYSICS_FOLLOWUPS)
        prompts = await generate_related_questions(
            Settings(), PHYSICS, "The force is 30 newtons.", allow_general=False
        )

    assert prompts == PHYSICS_FOLLOWUPS


async def test_the_model_may_return_no_follow_ups() -> None:
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(questions=[])
        prompts = await generate_related_questions(Settings(), SOURDOUGH, SOURDOUGH_REPLY)

    assert prompts == []


@pytest.mark.parametrize(
    "question",
    [
        "How do I remember vocabulary faster?",
        "What's the best to-do list app for students?",
        "Why do cats turn around before lying down?",
    ],
)
def test_a_question_that_only_sounds_like_a_command_still_counts(question: str) -> None:
    from app.modules.chat.related_questions import general_question

    assert general_question(question, SOURDOUGH_REPLY)


@pytest.mark.parametrize(
    "command",
    [
        "Remember that I'm vegetarian",
        "Add milk to my to-do list please",
        "Set a timer for 10 minutes",
        "Don't forget my dentist appointment on Friday",
    ],
)
def test_a_reminder_or_memory_command_gets_no_follow_ups(command: str) -> None:
    from app.modules.chat.related_questions import general_question

    assert not general_question(command, SOURDOUGH_REPLY)


async def test_a_vague_what_if_is_dropped_for_one_that_names_the_change() -> None:
    vague = "What if it was 5?"
    named = [
        "What if $3x + 3 = 5$?",
        "Why subtract 3 from both sides first?",
        "Could 3x + 3 = 3 have a negative x?",
    ]
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        complete.return_value = RelatedQuestions(questions=[vague, *named])
        prompts = await generate_related_questions(Settings(), "3x+3=3", "x = 0")

    assert vague not in prompts
    assert len(prompts) == 3


async def test_always_three_or_none_after_one_more_ask() -> None:
    with patch(
        "app.modules.chat.related_prompts.complete_structured",
        new_callable=AsyncMock,
    ) as complete:
        # The first ask keeps two; the second brings a third.
        complete.side_effect = [
            RelatedQuestions(questions=PHYSICS_FOLLOWUPS[:2]),
            RelatedQuestions(questions=[PHYSICS_FOLLOWUPS[2]]),
        ]
        prompts = await generate_related_questions(Settings(), PHYSICS, "The force is 30 newtons.")
        assert prompts == PHYSICS_FOLLOWUPS
        assert complete.await_count == 2
        retry = complete.await_args_list[1].kwargs["messages"][-1]["content"]
        assert PHYSICS_FOLLOWUPS[0] in retry and "different" in retry

        # Still two after the second ask: none, never a half list.
        complete.side_effect = [
            RelatedQuestions(questions=PHYSICS_FOLLOWUPS[:2]),
            RelatedQuestions(questions=PHYSICS_FOLLOWUPS[:2]),
        ]
        assert await generate_related_questions(Settings(), PHYSICS, "The force is 30.") == []


def test_follow_up_suggestions_are_on_by_default_and_can_be_turned_off() -> None:
    from app.models.orm import User
    from app.models.schemas import UserUpdate

    column = User.__table__.c.follow_up_suggestions_enabled
    assert column.default.arg is True and column.server_default is not None
    assert UserUpdate(follow_up_suggestions_enabled=False).follow_up_suggestions_enabled is False


# The reply seen live, whose follow-ups only repeated the card's questions.
_LAPTOP_CARD = (
    "To give you a recommendation that actually fits your needs, I need to know what "
    "you'll be doing with it and how much you're willing to spend. A student needs "
    "something different than a video editor or a gamer.\n\n```clarify\n"
    '{"when":"first","questions":[{"id":"budget","label":"Budget range","question":"What '
    'is your budget?","options":["Under $600","$600 - $1,200","$1,200 - $2,500","No '
    'limit"],"multi":false},{"id":"use","label":"Primary use","question":"What will you '
    'primarily use the laptop for?","options":["Web browsing & office work","Programming '
    '& development","Photo/video editing","Gaming"],"multi":false}]}\n```'
)


def test_a_reply_that_asks_with_a_card_gets_no_follow_ups() -> None:
    from app.modules.chat.related_questions import follow_up_topic

    question = "which laptop should I buy"
    assert follow_up_topic(question, _LAPTOP_CARD, None, allow_general=True) is None
    answered = (
        "For programming on a mid-range budget, the **MacBook Air M3** is the best all-round "
        "pick: it compiles fast, stays silent and lasts a full day on battery.\n\n"
        "- **Windows alternative:** the Dell XPS 14 has a great keyboard and screen.\n"
        "- **Budget pick:** a Lenovo IdeaPad with 16 GB of RAM handles most coding work.\n\n"
        "Whichever you choose, get at least 16 GB of RAM and a 512 GB SSD."
    )
    assert follow_up_topic(question, answered, None, allow_general=True) is not None
