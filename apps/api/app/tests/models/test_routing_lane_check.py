"""The routing lanes name only catalog models, checked as the API and the worker start.

A lane naming a model the catalog dropped raised ``KeyError`` mid-turn (the tool selector,
word problems, the maths read), and only one test noticed (review 2026-11-12 §3.2).
"""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

from app.models import model_catalog
from app.models.model_removal import check_routing_lanes, routing_lane_errors
from app.models.routing_lanes import ROUTING, lane_aliases

REMOVED = "glm-5.3-flash"


@pytest.fixture
def removed(monkeypatch: pytest.MonkeyPatch) -> str:
    """The catalog as it would be with ``REMOVED`` deleted from it, the lanes left alone."""
    kept = {alias: model for alias, model in model_catalog._BY_ID.items() if alias != REMOVED}
    monkeypatch.setattr(model_catalog, "_BY_ID", kept)
    return REMOVED


def test_the_lanes_name_only_catalog_models() -> None:
    assert routing_lane_errors() == []
    check_routing_lanes()
    named = dict(lane_aliases(ROUTING))
    assert named["math_backups['qwen-3.7-flash']"] == "glm-5.3-flash"
    assert named["tool_selectors[0]"] == ROUTING.tool_selectors[0]


def test_a_lane_naming_a_removed_model_fails_startup(removed: str) -> None:
    errors = routing_lane_errors()
    assert errors == [
        "ROUTING.math_backups['qwen-3.7-flash'] names 'glm-5.3-flash', "
        "which the model catalog does not have"
    ]
    with pytest.raises(RuntimeError, match=r"glm-5\.3-flash"):
        check_routing_lanes()


def test_a_read_naming_no_lane_is_an_error() -> None:
    lanes = replace(
        ROUTING, decided=MappingProxyType({**ROUTING.decided, "maths": ("math", "maths", "x")})
    )
    errors = routing_lane_errors(lanes)
    assert len(errors) == 2
    assert all("ROUTING.decided['maths']" in error for error in errors)
