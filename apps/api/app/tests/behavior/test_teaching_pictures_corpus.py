"""The questions that ask to see no picture (``teaching_pictures_corpus.json``).

Offline: the corpus is well formed, each maths figure it names is one the read can name,
and each chemistry name is in the question's own words, so the grounding that guards the
live draw would accept it. ``teaching_pictures_eval.py`` measures the real reads on it.
"""

from __future__ import annotations

from typing import get_args

import pytest

from app.modules.chemistry.figure import written_by_user
from app.modules.math.figure.request import FigureRequest
from app.tests.behavior.teaching_pictures_eval import load

CORPUS = load()
_KINDS = set(get_args(FigureRequest.model_fields["kind"].annotation))


@pytest.mark.parametrize("subject", ["maths", "chemistry"])
def test_each_subject_has_both_kinds_of_question(subject: str) -> None:
    entries = CORPUS[subject]
    ids = [entry["id"] for entry in entries]
    assert len(ids) == len(set(ids))
    assert sum(entry["draw"] for entry in entries) >= 10
    assert sum(not entry["draw"] for entry in entries) >= 10


@pytest.mark.parametrize("entry", CORPUS["maths"], ids=lambda e: e["id"])
def test_a_maths_figure_is_one_the_read_can_name(entry: dict[str, object]) -> None:
    assert ("kind" in entry) is entry["draw"]
    if entry["draw"]:
        assert entry["kind"] in _KINDS - {"none"}


@pytest.mark.parametrize(
    "entry", [e for e in CORPUS["chemistry"] if e["draw"]], ids=lambda e: e["id"]
)
def test_a_compound_is_named_in_the_user_s_own_words(entry: dict[str, str]) -> None:
    assert written_by_user(entry["name"], [entry["prompt"]])
