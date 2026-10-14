"""'Where is kenya' ends on the app's offline ```map card."""

from __future__ import annotations

import pytest

from app.modules.chat.prompt_builder import _strip_prompt_owned_fences, _style_format_hints
from app.modules.chat.prompt_constants import MAP_FENCE_HINT, where_is_place


@pytest.mark.parametrize(
    "text, place",
    [
        ("where is kenya", "kenya"),
        ("Where's Kenya?", "Kenya"),
        ("where’s kenya", "kenya"),
        ("wheres kenya", "kenya"),
        ("where is the eiffel tower", "the eiffel tower"),
        ("where is kenya located", "kenya"),
        ("where is mount kilimanjaro on the map", "mount kilimanjaro"),
        ("where exactly is Lesotho?", "Lesotho"),
        ("what country is timbuktu in", "timbuktu"),
        ("what continent is egypt in", "egypt"),
        ("show me where nepal is", "nepal"),
        ("can you tell me where Bhutan is", "Bhutan"),
        ("do you know where Addis Ababa is?", "Addis Ababa"),
        ("where in the world is Tuvalu", "Tuvalu"),
        ("where are the andes", "the andes"),
        ("where is somalia", "somalia"),
        ("where is the natural history museum", "the natural history museum"),
        ("where is the international date line", "the international date line"),
    ],
)
def test_where_is_place_finds_the_place(text: str, place: str) -> None:
    assert where_is_place(text) == place


@pytest.mark.parametrize(
    "text",
    [
        "where is my phone",
        "where are my keys",
        "where am I",
        "where are you",
        "where is it",
        "where is everyone",
        "where is everything",
        "where is someone when you need them",
        "where is home",
        "where is the error in my code",
        "where is the bug in this function",
        "where is the settings menu",
        "where is my order",
        "where is the nearest pharmacy",
        "where is the closest coffee shop",
        "where is the bathroom",
        "where was jesus born",
        "where do i start",
        "where can i buy a laptop",
        "where is the line between free speech and hate speech in law",
        "tell me about kenya",
    ],
)
def test_where_is_place_skips_things_not_on_a_map(text: str) -> None:
    assert where_is_place(text) is None


@pytest.mark.parametrize("style", ["short", "balanced", "detailed"])
def test_where_is_question_gets_map_hint_in_every_style(style: str) -> None:
    parts = _style_format_hints(
        query_text="where is kenya",
        style=style,
        is_day_plan=False,
        minimal_personal_context=False,
    )
    assert MAP_FENCE_HINT in parts


def test_other_questions_do_not_pay_for_the_map_hint() -> None:
    parts = _style_format_hints(
        query_text="tell me about kenya",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
    )
    assert MAP_FENCE_HINT not in parts


def test_map_fence_is_dropped_from_history_so_it_is_not_copied() -> None:
    reply = 'Kenya is in East Africa.\n\n```map\n{"place": "Kenya", "lat": 0.0, "lon": 37.9}\n```'
    assert _strip_prompt_owned_fences(reply).strip() == "Kenya is in East Africa."
