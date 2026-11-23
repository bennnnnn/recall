"""The translated questions the formal reader is measured on (``formal_corpus/translated``).

600 STEM corpus questions in Amharic, Arabic, Spanish, French and Hindi, kept from the model
reader experiment for the formal reader's next subjects. Each names its corpus entry, whose
answer the eval uses, so an id that no longer exists in the corpus would be measured against
nothing: every one must still be there.
"""

from __future__ import annotations

import json

import pytest

from app.tests.behavior.formal_eval import TRANSLATED_DIR, translated_questions
from app.tests.behavior.stem_sweep import load

_SUBJECTS = {"math": "math", "physics": "physics", "chemistry": "chemistry"}


@pytest.mark.parametrize("path", sorted(TRANSLATED_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_every_translated_question_names_a_corpus_entry(path) -> None:
    items = json.loads(path.read_text(encoding="utf-8"))
    assert items
    for item in items:
        ids = {entry.id for entry in load(_SUBJECTS[item["subject"]])}
        assert item["id"] in ids, f"{path.stem}: {item['id']}"
        assert item["prompt"].strip()


def test_the_physics_questions_carry_their_corpus_answers() -> None:
    questions = translated_questions("physics")
    assert {q.set for q in questions} == {
        f"{lang}-reader" for lang in ("am", "ar", "es", "fr", "hi")
    }
    assert len(questions) >= 150


def test_every_casual_rewording_keeps_its_corpus_entry_and_numbers() -> None:
    """The casual rewordings the cross-check is measured on (``cross_check_eval``): each
    names its corpus entry, carries its answer, and keeps every number of its question."""
    from app.tests.behavior.cross_check_eval import QA_CASES, numbers_kept
    from app.tests.behavior.cross_check_eval import load as casual

    entries = {entry.id: entry for entry in load("physics")}
    items = casual()
    assert len(items) >= 300
    assert {item["id"] for item in items} >= {case["id"] for case in QA_CASES}
    for item in items:
        if item["source"].startswith("qa-"):
            continue
        entry = entries[item["source"]]
        assert tuple(item["answer"]) == entry.answers[0], item["id"]
        assert numbers_kept(entry.prompt, item["prompt"]), item["id"]
