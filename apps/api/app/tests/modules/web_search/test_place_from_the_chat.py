"""A place question that points back at the chat is about the chat's place, not the user's.

Live 2026-11-06: after four turns on a Zanzibar trip, "whats the weather like there now" got
"I don't have your location yet", and the apostrophe-less "whats" read as a statement, so
nothing was searched.
"""

from __future__ import annotations

import pytest

from app.modules.web_search import needs_web_search, points_back_in_chat

_TRIP = [
    {"role": "user", "content": "im thinking of going to zanzibar in december"},
    {"role": "assistant", "content": "December is a good time for Zanzibar."},
]


@pytest.mark.parametrize(
    "message, back",
    [
        ("whats the weather like there now", True),
        ("hows the weather there", True),
        # The user's own place, whatever the chat was about.
        ("thanks! how far is it to the airport from here?", False),
        ("is it raining here", False),
        ("and what about near me", False),
        # "Is there …" points at no place, and a thing nearby is the user's (review of #2305).
        ("is there a pharmacy nearby", False),
        ("is there a good ramen place open", False),
        ("is there still a ferry there", True),
        # "It" or "that" names a thing, not a place (review of #2305).
        ("how far is it to the airport", False),
        ("is it raining today", False),
    ],
)
def test_a_place_question_points_back_at_the_chat(message: str, back: bool) -> None:
    assert points_back_in_chat(message, [*_TRIP, {"role": "user", "content": message}]) is back


def test_with_no_chat_before_it_nothing_points_back() -> None:
    assert points_back_in_chat("whats the weather like there now", []) is False


@pytest.mark.parametrize(
    "message", ["whats the weather like there now", "hows the weather in zanzibar today"]
)
def test_a_question_typed_without_its_apostrophe_still_searches(message: str) -> None:
    assert needs_web_search(message) is True
