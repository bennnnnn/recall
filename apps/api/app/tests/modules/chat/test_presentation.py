"""Reply presentation: the shared corpus, plus the server-only orphan-answer rule.

`docs/fixtures/presentation_cases.json` holds every presentation case both sides
must agree on: REPL transcripts, word spaces outside inline tokens, inline code
against maths, and one calculation state per row. This test presents each input
with `present_assistant_markdown` and expects the output exactly; the phone test
(`lib/__tests__/presentationCorpus.test.ts`) does the same with
`presentAssistantMarkdown`. A presented row presents to itself, which is why the
phone can leave a persisted row as the server saved it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.modules.chat.calculation_layout import split_math_expression
from app.modules.chat.presentation import drop_orphan_leading_answer, present_assistant_markdown

FIXTURE = Path(__file__).resolve().parents[6] / "docs" / "fixtures" / "presentation_cases.json"
CASES: list[dict[str, Any]] = json.loads(FIXTURE.read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_presentation_corpus_case(case: dict[str, Any]) -> None:
    assert present_assistant_markdown(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_presented_text_presents_to_itself(case: dict[str, Any]) -> None:
    assert present_assistant_markdown(case["expected"]) == case["expected"]


def test_corpus_ids_are_unique_and_every_area_is_covered() -> None:
    ids = [case["id"] for case in CASES]
    assert len(ids) == len(set(ids))
    areas = {case["area"] for case in CASES}
    assert areas == {
        "boundaries",
        "inline_code",
        "calculation",
        "maths",
        "fences",
        "lists",
        "repl",
        "replies",
    }


def test_a_why_question_drops_the_previous_sum() -> None:
    question = (
        "Why does adding two positive numbers always result in a larger number "
        "than either of the original numbers?"
    )
    reply = "7\n\nAdding two positive numbers moves further along the number line."
    assert drop_orphan_leading_answer(reply, question) == (
        "Adding two positive numbers moves further along the number line."
    )
    fenced = "```answer\n7\n```\n\nAdding two positive numbers moves further along the number line."
    assert "7" not in drop_orphan_leading_answer(fenced, question)
    assert drop_orphan_leading_answer("7", "What is 3 + 4?") == "7"


def test_split_math_expression_rows() -> None:
    rows = split_math_expression(r"t_{\text{total}} = d/60 + d/40 = (2d+3d)/120 = 5d/120")
    assert rows == [
        r"t_{\text{total}} = d/60 + d/40",
        r"t_{\text{total}} = (2d+3d)/120",
        r"t_{\text{total}} = 5d/120",
    ]
    assert split_math_expression("f(x, y) = 1") is None
    assert split_math_expression(r"\begin{aligned} a &= b \end{aligned}") is None
