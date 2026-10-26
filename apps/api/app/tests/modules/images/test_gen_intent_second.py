"""A draw-me line with a second request is declined exactly where the plan cuts it.

``asks_separately`` keeps "draw me a cat and also explain black holes" from drawing the
whole line: the plan draws the cat and answers the rest. It must agree with the plan. A
line it declines that the plan keeps whole draws nothing at all (main drew it: "draw me
a dog and tell me about dog breeds"); a line the plan cuts that it lets through draws the
whole line, question and all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.images.gen_intent import extract_image_gen_prompt
from app.modules.images.gen_intent_second import SECOND_ASKS, asks_separately
from app.tests.behavior.cases import CASES

_SWEEP = Path(__file__).resolve().parents[2] / "behavior" / "sweep_corpus"

# Kept whole by the plan, so drawn whole, as on main.
WHOLE = [
    "Draw me a dog and tell me about dog breeds",
    "Draw me a cat and tell me about cat breeds",
    "draw me a car and tell me which car is fastest",
    "draw me a cat and show the cat sleeping",
    "draw me a cat and how are you",
    "draw me a cat and tell me its name",
    "draw me a castle and help",
]
# Cut by the plan: the cat is drawn and the rest answered beside it.
CUT = [
    "draw me a cat and also explain black holes",
    "draw me a cat and explain black holes",
    "Draw me a dog and also tell me about dog breeds",
    "draw me a cat and tell me about cats",
    "draw me a sunset and what time is it in Tokyo",
    "draw me a robot and write a haiku about autumn",
]


def _plan_cuts(text: str) -> bool:
    plan = plan_turn(text)
    return plan.multi and [part.kind for part in plan.parts][:1] == ["image"]


def _subject_tokens(text: str) -> list[str]:
    """The words after "draw me (a)", as the draw-me reader hands them over."""
    tokens = text.split()[2:]
    return tokens[1:] if tokens and tokens[0].lower() in {"a", "an", "the"} else tokens


def _corpus_lines() -> list[str]:
    """Every draw-me line with "and" before an answer word in the sweep and battery."""
    prompts = {case.prompt for case in CASES}
    for path in _SWEEP.glob("*.json"):
        prompts.update(entry["prompt"] for entry in json.loads(path.read_text()))
    return sorted(
        text
        for text in prompts
        if text.lower().startswith("draw me ")
        and any(f" and {ask} " in f" {text.lower()} " for ask in SECOND_ASKS)
    )


@pytest.mark.parametrize("text", WHOLE)
def test_a_line_the_plan_keeps_whole_draws_whole(text: str) -> None:
    assert not _plan_cuts(text)
    assert extract_image_gen_prompt(text)


@pytest.mark.parametrize("text", CUT)
def test_a_line_the_plan_cuts_draws_only_the_picture_part(text: str) -> None:
    assert _plan_cuts(text)
    assert extract_image_gen_prompt(text) is None


@pytest.mark.parametrize("text", [*WHOLE, *CUT, *_corpus_lines()])
def test_asks_separately_agrees_with_the_plan(text: str) -> None:
    assert asks_separately(_subject_tokens(text)) == _plan_cuts(text)
