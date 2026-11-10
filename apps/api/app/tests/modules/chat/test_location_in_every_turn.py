"""Where the user is, in every turn while Location gives a place.

"Where is the nearest Apple Store?" used the phone's place; a minute later "Can i wolk?"
asked for a starting point and "Current location" said it could not see one (2026-11-09).
Both were slim turns, whose prompt states the place only for a location-worded message, and
the profile block said not to quote it. The model reads any wording: the place is stated,
with when to use it, and the model decides.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.core.config import get_settings
from app.modules.chat.prompt_context_hints import slim_geo_hints
from app.modules.chat.prompt_profile import USE_THE_LOCATION, format_user_profile_block
from app.tests.fakes import make_user

PLACE = "Oakland, California, United States"


def saved(place: str | None) -> Any:
    """A user whose phone saved ``place`` a minute ago."""
    return make_user(
        location=place,
        location_enabled=True,
        location_saved_at=datetime.now(UTC) - timedelta(minutes=1) if place else None,
    )


@pytest.mark.parametrize(
    "message", ["Can i wolk?", "Current location", "how long to get there", "is it far"]
)
def test_a_slim_turn_states_the_users_place_whatever_the_wording(message: str) -> None:
    parts = slim_geo_hints(get_settings(), message, None, saved(PLACE), "UTC")
    assert parts[0] == f"The user's location: {PLACE}. {USE_THE_LOCATION}"


def test_a_slim_turn_prefers_the_fix_the_turn_carries() -> None:
    parts = slim_geo_hints(
        get_settings(), "Can I walk?", "Jack London Square, Oakland", saved(PLACE), "UTC"
    )
    assert parts[0].startswith("The user's location: Jack London Square, Oakland. ")


def test_a_slim_turn_states_no_place_without_one() -> None:
    assert slim_geo_hints(get_settings(), "Can I walk?", None, saved(None), "UTC") == []


def test_the_place_does_not_wait_for_web_search() -> None:
    """Where the user is answers "where am I" and "is it far" with search off too."""
    search_off = get_settings().model_copy(update={"web_search_enabled": False})
    assert slim_geo_hints(search_off, "Current location", None, saved(PLACE), "UTC") == [
        f"The user's location: {PLACE}. {USE_THE_LOCATION}"
    ]


@pytest.mark.parametrize(
    "saved_ago, says_to_use",
    [(timedelta(minutes=1), True), (timedelta(hours=5), True), (timedelta(hours=30), False)],
)
def test_the_profile_says_to_use_the_place_while_it_lists_one(
    saved_ago: timedelta, says_to_use: bool
) -> None:
    user = make_user(
        location=PLACE, location_enabled=True, location_saved_at=datetime.now(UTC) - saved_ago
    )
    block = format_user_profile_block(user)
    assert (USE_THE_LOCATION in block) is says_to_use
    # A "who am I" answer still never recites it, and the header no longer forbids using it.
    assert "never recite email or location in a general 'who am I' answer" in block
    assert "do not quote email or location" not in block
