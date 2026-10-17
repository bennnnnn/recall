"""Multi-step rate word problems think; one-step questions and errands stay fast."""

import pytest

from app.core.config import Settings
from app.services import model_catalog
from app.services.rate_problems import is_multi_step_rate_problem
from app.services.routing import message_needs_thinking, route_chat_model

TRAIN = (
    "A train leaves at 3pm going 80 km/h; another leaves the same station at 4pm going "
    "120 km/h on the same track. When and where does the second catch the first?"
)
HARD = [
    TRAIN,
    "A cyclist has a 2 km head start at 15 km/h. A runner chases at 20 km/h. "
    "How long until he overtakes her?",
    "A boat goes 24 km upstream in 3 hours and back downstream in 2 hours. "
    "Find the speed of the current.",
    "Two painters working together finish the wall in 4 hours; one alone takes 6. "
    "How long does the other take?",
]
EASY = [
    "John drove 20 km in 2 hours. What is his speed?",
    "A bike travels 45 km in 3 hours. What's its average speed?",
    "Let's meet at 3pm tomorrow, I have 2 meetings before",
    "My train leaves at 3pm, remind me at 2:30",
    "What time does the 4pm train from Boston get to New York?",
    "We worked together for 3 years at 2 companies",
    "Can we meet at 3 or 4?",
]


@pytest.mark.parametrize("text", HARD)
def test_is_multi_step_rate_problem_reads_pursuit_current_and_joint_work(text: str) -> None:
    assert is_multi_step_rate_problem(text)


@pytest.mark.parametrize("text", EASY)
def test_is_multi_step_rate_problem_leaves_one_step_and_errands(text: str) -> None:
    assert not is_multi_step_rate_problem(text)


def test_the_train_catch_up_turns_thinking_on() -> None:
    # With thinking off the smart model answered 7pm, 320 km; the answer is 6pm, 240 km.
    settings = Settings()
    assert route_chat_model(TRAIN, settings=settings) == model_catalog.auto_smart_alias()
    assert message_needs_thinking(TRAIN, settings=settings)


@pytest.mark.parametrize("text", EASY)
def test_one_step_and_errand_turns_keep_thinking_off(text: str) -> None:
    assert not message_needs_thinking(text, settings=Settings())


def test_a_verified_meeting_problem_stays_on_the_fast_lane() -> None:
    # The physics solver closes this one, so it needs no thinking pass.
    text = (
        "Two cars start 300 km apart and drive toward each other at 60 km/h and 90 km/h. "
        "When do they meet?"
    )
    assert not message_needs_thinking(text, settings=Settings())
