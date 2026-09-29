"""Continuation turns keep the prior subject's presentation contract."""

from types import SimpleNamespace
from uuid import uuid4

from app.modules.math.followup import is_math_followup
from app.modules.math.reply_policy import MATH_REPLY_POLICY
from app.modules.physics.extract import needs_physics
from app.services.chat.continuation_subject import (
    classify_presentation_subject,
    effective_presentation_subject,
    is_pure_continuation,
)
from app.services.chat.prompt_builder import _style_format_hints
from app.services.chat.prompt_constants import (
    BIOLOGY_PRESENTATION_HINT,
    CHEMISTRY_PRESENTATION_HINT,
    MATH_INTENT_HINT,
    PHYSICS_INTENT_HINT,
    STATISTICS_PRESENTATION_HINT,
)
from app.services.routing import route_chat_model
from app.services.subject_solving import detect_subject

CYCLIST = "A cyclist rides 12 km at 20 km/h then 8 km at 10 km/h. Find average speed."
EQUATION = "Solve 2x + 3 = 11"
STATS = "The values are 2, 4, 6 and 8. Find the sample mean."
BIOLOGY = "In a Punnett square, 1 of 4 offspring shows the recessive allele."
CHEMISTRY = "Balance H2 + O2 -> H2O"


def _exchange(*turns: tuple[str, str]) -> list[tuple[str, str]]:
    return list(turns)


def test_another_is_not_itself_a_subject() -> None:
    assert detect_subject("Another") is None
    assert classify_presentation_subject("Another") is None
    assert is_pure_continuation("Another")
    assert is_pure_continuation("Trickier")
    assert is_pure_continuation("One more")
    assert is_pure_continuation("Same but harder")
    assert not is_pure_continuation("How do plants grow?")
    assert not is_pure_continuation("explain photosynthesis")
    assert not is_pure_continuation("Write me an email")


def test_physics_continuation_keeps_physics_and_a_new_topic_does_not() -> None:
    assert needs_physics(CYCLIST)
    prior = _exchange(("user", CYCLIST), ("assistant", "The average speed is 48 km/h."))
    assert effective_presentation_subject("Another", prior) == "physics"
    assert effective_presentation_subject("Trickier", prior) == "physics"
    assert effective_presentation_subject("please give me another", prior) == "physics"
    chained = [
        *prior,
        ("user", "Another"),
        ("assistant", "Here is a harder ride."),
    ]
    assert effective_presentation_subject("Trickier", chained) == "physics"
    assert effective_presentation_subject("Write me an email", prior) is None
    assert effective_presentation_subject("How do plants grow?", prior) is None
    france = [
        *prior,
        ("user", "What is the capital of France?"),
        ("assistant", "Paris."),
    ]
    assert effective_presentation_subject("Another", france) is None


def test_math_chemistry_statistics_and_biology_continuations() -> None:
    assert effective_presentation_subject(
        "One more", [("user", EQUATION), ("assistant", "x = 4")]
    ) == ("math")
    assert effective_presentation_subject(
        "Harder", [("user", CHEMISTRY), ("assistant", "2 H2O")]
    ) == ("chemistry")
    assert effective_presentation_subject("Another", [("user", STATS), ("assistant", "5")]) == (
        "statistics"
    )
    assert effective_presentation_subject(
        "Another", [("user", BIOLOGY), ("assistant", "100 fold")]
    ) == ("biology")


def test_style_hints_follow_the_continuation_subject() -> None:
    physics_prior = [("user", CYCLIST), ("assistant", "48 km/h")]
    another = _style_format_hints(
        query_text="Another",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        prior_messages=physics_prior,
    )
    assert PHYSICS_INTENT_HINT in another
    assert MATH_REPLY_POLICY not in another

    email = _style_format_hints(
        query_text="Write me an email",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        prior_messages=physics_prior,
    )
    assert PHYSICS_INTENT_HINT not in email

    math_hints = _style_format_hints(
        query_text="One more",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        prior_messages=[("user", EQUATION), ("assistant", "x = 4")],
    )
    assert MATH_INTENT_HINT in math_hints
    assert math_hints[-1] == MATH_REPLY_POLICY

    chemistry = _style_format_hints(
        query_text="Another",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        prior_messages=[("user", CHEMISTRY), ("assistant", "2 H2O")],
    )
    assert CHEMISTRY_PRESENTATION_HINT in chemistry
    assert MATH_REPLY_POLICY not in chemistry

    statistics = _style_format_hints(
        query_text="Another",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        prior_messages=[("user", STATS), ("assistant", "5")],
    )
    assert STATISTICS_PRESENTATION_HINT in statistics

    biology = _style_format_hints(
        query_text="Another",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        prior_messages=[("user", BIOLOGY), ("assistant", "100 fold")],
    )
    assert BIOLOGY_PRESENTATION_HINT in biology


def test_how_after_physics_is_not_a_math_solver_replay() -> None:
    recent = [
        SimpleNamespace(id=uuid4(), role="user", content=CYCLIST),
        SimpleNamespace(id=uuid4(), role="assistant", content="48 km/h"),
    ]
    assert is_math_followup("How?", recent) is False
    math_recent = [
        SimpleNamespace(id=uuid4(), role="user", content=EQUATION),
        SimpleNamespace(id=uuid4(), role="assistant", content="```answer\nx = 4\n```"),
    ]
    assert is_math_followup("How?", math_recent) is True
    assert is_math_followup("Another", math_recent) is False


def test_another_inherits_the_strong_model_after_a_hard_turn() -> None:
    prior = "a block slides down a 90° frictionless incline, find its acceleration"
    assert route_chat_model("Another", prior_user=prior) == "smart-chat"
    assert route_chat_model("Write me an email", prior_user=prior) == route_chat_model(
        "Write me an email"
    )
    assert route_chat_model("explain photosynthesis", prior_user="debug this algorithm") == (
        "gemini-flash"
    )
