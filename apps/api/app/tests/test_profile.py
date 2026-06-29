"""Tests for profile name normalization."""

import pytest

from app.models.schemas import UserUpdate
from app.services.profile import normalize_display_name


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
