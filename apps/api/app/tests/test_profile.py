"""Tests for profile name normalization."""

import pytest

from app.models.schemas import UserUpdate
from app.services.profile import (
    effective_location_label,
    normalize_client_coordinates,
    normalize_client_location,
    normalize_display_name,
    user_location_label,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("  Ada   Lovelace  ", "Ada Lovelace"),
        ("Cher", "Cher"),
        ("", None),
        ("   ", None),
        ("x" * 81, None),
        (None, None),
    ],
)
def test_normalize_display_name(raw: str | None, expected: str | None):
    assert normalize_display_name(raw) == expected


def test_user_update_normalizes_name():
    update = UserUpdate(name="  Grace   Hopper  ")
    assert update.name == "Grace Hopper"


def test_user_update_rejects_blank_name():
    with pytest.raises(ValueError):
        UserUpdate(name="   ")


def test_user_location_label_requires_enabled():
    class U:
        location_enabled = False
        location = "Oakland, CA"

    assert user_location_label(U()) is None


def test_user_location_label_when_enabled():
    class U:
        location_enabled = True
        location = "  Oakland, CA  "

    assert user_location_label(U()) == "Oakland, CA"


def test_normalize_client_location():
    assert normalize_client_location("  San Francisco, CA  ") == "San Francisco, CA"
    assert normalize_client_location("") is None
    assert normalize_client_location("x" * 201) is None


def test_effective_location_label_ignores_client_when_disabled():
    class U:
        location_enabled = False
        location = None

    assert effective_location_label(U(), "San Francisco, CA") is None


def test_effective_location_label_prefers_client_when_enabled():
    class U:
        location_enabled = True
        location = "Oakland, CA"

    assert effective_location_label(U(), "San Francisco, CA") == "San Francisco, CA"


def test_effective_location_label_falls_back_to_profile():
    class U:
        location_enabled = True
        location = "Oakland, CA"

    assert effective_location_label(U(), None) == "Oakland, CA"


def test_normalize_client_coordinates():
    assert normalize_client_coordinates(37.8, -122.4) == (37.8, -122.4)
    assert normalize_client_coordinates(None, None) is None
    assert normalize_client_coordinates(37.8, None) is None
    assert normalize_client_coordinates(91.0, 0.0) is None
