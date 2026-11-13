"""A model a request picks is a catalog alias or Auto, in every body that takes one.

An alias the catalog really had and dropped reads as Auto (``models/model_removal.py``);
any other name is refused."""

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.models.model_catalog import selectable_models
from app.models.schemas.auth import UserUpdate
from app.models.schemas.chats import ChatCreate, ChatMessageRequest

_BODIES: list[tuple[type[BaseModel], str]] = [
    (UserUpdate, "default_model"),
    (ChatCreate, "model"),
    (ChatMessageRequest, "model"),
]


@pytest.mark.parametrize(("body", "field"), _BODIES)
@pytest.mark.parametrize("choice", ["auto", "known"])
def test_a_known_alias_or_auto_is_taken(body: type[BaseModel], field: str, choice: str) -> None:
    alias = choice if choice == "auto" else selectable_models()[0].id
    assert getattr(body.model_validate({field: alias}), field) == alias


@pytest.mark.parametrize(("body", "field"), _BODIES)
@pytest.mark.parametrize("removed", ["glm-5.2", "gpt-6-sol", "qwen-plus"])
def test_an_alias_the_catalog_removed_is_auto(
    body: type[BaseModel], field: str, removed: str
) -> None:
    """A model removed since the phone saved it: the message still goes, on Auto."""
    assert getattr(body.model_validate({field: removed}), field) == "auto"


@pytest.mark.parametrize(("body", "field"), _BODIES)
@pytest.mark.parametrize(
    "name",
    # A name shaped like an alias is still no alias: a typo, another app's model, a lane
    # that was never one, or a made-up word.
    ["nope", "fake-model", "gpt-4o", "smart-chta", "image-search-model", "No pe!"],
)
def test_an_unknown_alias_is_refused(body: type[BaseModel], field: str, name: str) -> None:
    with pytest.raises(ValidationError, match=f"Unknown model alias: {name}"):
        body.model_validate({field: name})


@pytest.mark.parametrize(
    ("body", "field", "default"),
    [
        (UserUpdate, "default_model", None),
        (ChatCreate, "model", "auto"),
        (ChatMessageRequest, "model", None),
    ],
)
def test_an_unsent_model_keeps_its_default(body: type[BaseModel], field: str, default: Any) -> None:
    assert getattr(body.model_validate({}), field) == default
