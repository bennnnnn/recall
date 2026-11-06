"""A physics answer is the quantity asked, and its picture is titled by what happens.

2026-11-06: "a 2kg rock falls from a 15m cliff, ignore air. speed just before it hits the
ground using energy" asks with no verb and no "?", so nothing was read as asked and the fall's
extractor answered its default, a checked 1.75 s. A two-part answer written "**Answer (a):**
20.4 m" kept its lines and a closing card said "20.4 m; 4.08 s" again, and a ball thrown
straight up was drawn under "Free Fall".
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.ask import ask_clause, asked_phrases, has_ask
from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.fence import validate_physics_fences
from app.modules.physics.solvers.motion_scenes import vertical_scene
from app.services.part_answer_cards import own_line_part_answers
from app.services.subjects.dispatch import build_subject_augmentation


@pytest.mark.parametrize(
    ("text", "asked"),
    [
        (
            "new one. a 2kg rock falls from a 15m cliff, ignore air. "
            "speed just before it hits the ground using energy",
            ("speed",),
        ),
        ("a rock falls from a 15m cliff. velocity just before it hits the ground", ("velocity",)),
        ("a ball dropped from 20 m. time to hit the ground", ("time",)),
        ("a 2 kg ball dropped from 20 m. kinetic energy just before impact", ("kinetic energy",)),
        ("a ball dropped from 20 m, speed after 1.5 s", ("speed",)),
    ],
)
def test_a_closing_phrase_that_names_a_quantity_asks_it(text: str, asked: tuple[str]) -> None:
    assert asked_phrases(text) == asked
    assert has_ask(text)


@pytest.mark.parametrize(
    "text",
    [
        "a ball is dropped from 80 m.",
        "a car moves at 20 m/s. mass 1200 kg",
        "the speed of the car is 20 m/s.",
        "A car of mass 1200 kg, speed 20 m/s",
    ],
)
def test_a_closing_phrase_that_states_a_value_asks_nothing(text: str) -> None:
    assert ask_clause(text) is None


@pytest.mark.parametrize(
    ("text", "op"),
    [
        (
            "new one. a 2kg rock falls from a 15m cliff, ignore air. "
            "speed just before it hits the ground using energy",
            "speed",
        ),
        ("a rock falls from a 15m cliff. velocity just before it hits the ground", "velocity"),
        ("a ball dropped from 20 m. time to hit the ground", "time_to_ground"),
    ],
)
def test_the_fall_answers_the_quantity_asked(text: str, op: str) -> None:
    intent = extract_physics_intent(text)
    assert intent is not None and intent.physics_op == op


@pytest.mark.parametrize(
    ("v0", "title", "key"),
    [
        (20.0, "Thrown Upward", "thrown_up"),
        (0.0, "Free Fall", "free_fall"),
        (-5.0, "Thrown Downward", "thrown_down"),
    ],
)
def test_a_vertical_scene_is_titled_by_its_launch(v0: float, title: str, key: str) -> None:
    scene = vertical_scene(30.0, v0, 9.81, 2.0, ground=True)
    assert scene is not None
    assert (scene.title, scene.title_key) == (title, key)
    assert ("down" in scene.alt) == (v0 < 0)


def test_a_part_answer_on_its_heading_line_moves_under_it() -> None:
    text = "**Answer (a):** $20.4\\,\\mathrm{m}$\n\n```\n**Answer (b):** in code\n```"
    assert own_line_part_answers(text) == (
        "**Answer (a)**\n\n$20.4\\,\\mathrm{m}$\n\n```\n**Answer (b):** in code\n```"
    )


async def test_each_part_is_carded_once_when_its_value_shares_the_heading_line() -> None:
    question = (
        "a ball is thrown straight up at 20 m/s. how high does it go and how long till it "
        "comes back down"
    )
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    verified = (await build_subject_augmentation(question, settings)).verified
    reply = (
        "**(a) Maximum height**\n\n$h_{\\max} = \\frac{400}{19.62} = 20.4\\,\\mathrm{m}$\n\n"
        "**Answer (a):** $20.4\\,\\mathrm{m}$\n\n---\n\n**(b) Time to return**\n\n"
        "$t = \\frac{40}{9.81} = 4.08\\,\\mathrm{s}$\n\n**Answer (b):** $4.08\\,\\mathrm{s}$\n\n"
        "**Answer**\n\n```answer\n20.4 m; 4.08 s\n```"
    )
    out = validate_physics_fences(reply, verified=verified, user_text=question)
    cards = out.count("```answer")
    assert cards == 2
    assert "20.4\\,\\mathrm{m}\n```" in out and "4.08\\,\\mathrm{s}\n```" in out
    assert ";" not in out.split("```simulation")[0]
    assert '"title_key":"thrown_up"' in out
