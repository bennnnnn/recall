"""What the app reads about plans: the user's features."""

from datetime import datetime
from uuid import uuid4

import pytest

from app.main import create_app
from app.models.schemas import UserOut


@pytest.mark.parametrize(
    "plan_id, has_live_talk, has_voice",
    [("free", False, False), ("pro", True, True)],
)
def test_user_payload_lists_plan_features(plan_id, has_live_talk, has_voice):
    out = UserOut(
        id=uuid4(),
        email="a@b.c",
        name=None,
        avatar_url=None,
        default_model="auto",
        plan=plan_id,
        memory_enabled=True,
        created_at=datetime(2026, 1, 1),
    )
    body = out.model_dump()
    assert ("live_talk" in body["features"]) is has_live_talk
    assert ("speech_transcription" in body["features"]) is has_voice
    assert "image_generation" in body["features"]


def test_the_plan_catalog_route_is_gone():
    """Nothing read ``GET /billing/plans``: the plans page words the benefits itself."""
    paths = create_app().openapi()["paths"]
    assert not any(path.startswith("/billing") for path in paths)
