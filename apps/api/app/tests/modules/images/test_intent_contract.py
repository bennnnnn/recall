"""The server reads composer image intent exactly the way the phone does.

`docs/fixtures/image_intent_cases.json` holds every phrase both sides must agree
on: what it generates, how it revises the last picture, and whether it wants a
real photo. The mobile test (`features/images/model/__tests__/imageIntentContract.test.ts`)
asserts the same cases, so a rule changed on one side alone fails a suite.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.modules.images.gen_intent import (
    extract_image_gen_prompt,
    extract_image_gen_prompt_from_thread,
    extract_image_revision_prompt,
    image_gen_revision_context,
)
from app.modules.images.lookup_intent import extract_image_lookup_query

FIXTURE = Path(__file__).resolve().parents[6] / "docs" / "fixtures" / "image_intent_cases.json"
CASES: dict[str, Any] = json.loads(FIXTURE.read_text())
PREVIOUS_SUBJECT: str = CASES["revise_previous_subject"]


def _id(case: dict[str, Any]) -> str:
    return repr(case["text"])[:60]


@pytest.mark.parametrize("case", CASES["phrases"], ids=_id)
def test_intent_contract_phrase(case: dict[str, Any]) -> None:
    text = case["text"]
    assert extract_image_gen_prompt(text) == case["generate"]
    assert extract_image_lookup_query(text) == case["lookup"]
    assert (
        extract_image_revision_prompt(
            text,
            last_assistant_is_image_only=True,
            previous_subject=PREVIOUS_SUBJECT,
        )
        == case["revise"]
    )


@pytest.mark.parametrize("case", CASES["threads"], ids=_id)
def test_intent_contract_thread(case: dict[str, Any]) -> None:
    assert extract_image_gen_prompt_from_thread(case["text"], case["priors"]) == case["generate"]


@pytest.mark.parametrize("case", CASES["revision_contexts"])
def test_intent_contract_revision_context(case: dict[str, Any]) -> None:
    assert image_gen_revision_context(case["messages"]) == (
        case["last_assistant_is_image_only"],
        case["previous_subject"],
    )
