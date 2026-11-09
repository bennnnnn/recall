"""A place the phone saved a while ago is said as its last report, never as where the user is.

"Where am I?" with no fix answered a saved city of any age, and the weather in New York
that evening read San Francisco from the morning as current (review, 2026-11-09).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.chat.turn_prep.request import ClientGeoContext
from app.modules.chat.turn_prep.saved_place import (
    last_report_answer,
    last_reported_place,
    saved_place,
)
from app.tests.fakes import make_user

_NOW = datetime(2026, 11, 9, 20, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "age, place, as_of",
    [
        (timedelta(minutes=20), "San Francisco, CA", False),
        (timedelta(hours=9), "San Francisco, CA", True),
        (timedelta(hours=30), None, False),
    ],
)
def test_a_saved_place_by_its_age(age: timedelta, place: str | None, as_of: bool) -> None:
    saved_at = _NOW - age
    user = make_user(
        location_enabled=True, location="San Francisco, CA", location_saved_at=saved_at
    )
    assert saved_place(user, _NOW) == (place, saved_at if as_of else None)


def test_an_old_saved_place_is_said_as_the_phones_last_report() -> None:
    as_of = datetime.now(UTC) - timedelta(hours=6)
    answer = last_report_answer("San Francisco, CA", as_of, "America/New_York")
    assert answer.startswith("Your phone last reported **San Francisco, CA**, at ")
    assert "about 6 hours ago" in answer
    described = last_reported_place("San Francisco, CA", as_of, "America/New_York")
    assert described.startswith("San Francisco, CA (where the phone last reported, at ")
    assert "may have moved" in described


def test_the_prompt_gives_an_old_place_as_the_last_report_and_a_current_one_plainly() -> None:
    def geo(as_of: datetime | None) -> ClientGeoContext:
        return ClientGeoContext(
            user_location="San Francisco, CA",
            client_lat=None,
            client_lng=None,
            has_geo_fix=True,
            geo_query=True,
            ambiguous_nearby=False,
            local_places=False,
            place_as_of=as_of,
        )

    assert geo(None).prompt_place("UTC") == "San Francisco, CA"
    old = geo(datetime.now(UTC) - timedelta(hours=5)).prompt_place("UTC")
    assert old is not None and old.startswith("San Francisco, CA (where the phone last reported")
