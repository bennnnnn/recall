"""``$$`` display maths, read the same on the server as on the phone.

``docs/fixtures/display_math_cases.json`` holds the cases both run (the phone's test is
apps/mobile/lib/__tests__/displayDollars.test.ts): price tiers ("$$-$$$", "Zuni - $$.")
are no maths, and a formula opens at a line's start or as a tight ``$$x$$``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.chat.calculation_layout import layout_calculations
from app.modules.chat.display_dollars import (
    Closer,
    display_dollar_pair_end,
    find_display_dollars,
    scan_display_line,
)
from app.modules.chat.inline_boundaries import repair_inline_token_boundaries
from app.modules.chat.markdown_regions import display_math_lines
from app.modules.chat.math_padding import maths_pair_end
from app.modules.chat.notation_spans import code_notation
from app.tests.behavior.latex_check import _maths_and_prose

FIXTURE = Path(__file__).resolve().parents[6] / "docs" / "fixtures" / "display_math_cases.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
IDS = [case["id"] for case in CASES]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_display_dollars_pair_end_pairs_the_same_dollars(case: dict[str, object]) -> None:
    text = str(case["text"])
    found: list[str] = []
    index = 0
    while index < len(text):
        end = display_dollar_pair_end(text, index) if text.startswith("$$", index) else None
        if end is None:
            index += 1
            continue
        found.append(text[index + 2 : end - 2].strip())
        index = end
    assert found == case["display"]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_display_dollars_latex_check_reads_the_same_maths(case: dict[str, object]) -> None:
    maths, _prose = _maths_and_prose(str(case["text"]))
    assert [body.strip() for body in maths] == case["display"]


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (["$$", "x = 1", "$$", "after"], [True, True, True, False]),
        (["\\[", "a", "\\]", "after"], [True, True, True, False]),
        (["\\$$ not maths", "next"], [False, False]),
        (["$$x \\$$", "y", "$$"], [True, True, True]),
        (["$$x \\\\$$", "next"], [False, False]),
        (["`$$` code", "next"], [False, False]),
        (["Nopa – $$.", "Zuni – $$$.", "Bar – $$."], [False, False, False]),
        (["- $$ = moderate", "- $$$ = pricey", "after"], [True, False, False]),
    ],
)
def test_display_dollars_lines_match_the_phone(lines: list[str], expected: list[bool]) -> None:
    """The phone's lib/__tests__/markdownRegions.test.ts holds the same lines."""
    assert display_math_lines(lines) == expected


def test_display_dollars_price_range_is_no_formula() -> None:
    assert display_dollar_pair_end("Californian, $$-$$$, open late.", 13) is None


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_display_dollars_lines_cover_the_fixture_formulas(case: dict[str, object]) -> None:
    """``display_math_lines`` marks every line a formula over several lines covers; with no
    formula left open or ended unclosed, it marks no other."""
    text = str(case["text"])
    lines = text.split("\n")
    marks = display_math_lines(lines)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line) + 1)

    def line_of(offset: int) -> int:
        return max(index for index, start in enumerate(starts) if start <= offset)

    covered: set[int] = set()
    for start, end in find_display_dollars(text):
        first, last = line_of(start), line_of(end - 1)
        if first != last:
            covered |= set(range(first, last + 1))
    assert all(marks[index] for index in covered)
    heard: list[str] = []
    closer: Closer = None
    for line in lines:
        closer = scan_display_line(line, closer, True, lambda kind, _at: heard.append(kind))
    if closer is None and "drop" not in heard:
        assert {index for index, mark in enumerate(marks) if mark} == covered


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_display_dollars_find_reads_the_fixture(case: dict[str, object]) -> None:
    text = str(case["text"])
    found = [text[start + 2 : end - 2].strip() for start, end in find_display_dollars(text)]
    assert found == case["display"]


# One-line texts with dollar runs and no formula: prices. Each pass that reads ``$$`` asks the
# shared reader, so reverting one to its own pairing fails its test here (the phone's twin is
# apps/mobile/lib/__tests__/displayDollarsWiring.test.ts).
PRICES = [
    case
    for case in CASES
    if not case["display"]
    and "\n" not in case["text"]
    and "`" not in case["text"]
    and "\\" not in case["text"]
]
PRICE_IDS = [case["id"] for case in PRICES]


@pytest.mark.parametrize("case", PRICES, ids=PRICE_IDS)
def test_display_dollars_inline_boundaries_leave_a_price(case: dict[str, object]) -> None:
    assert repair_inline_token_boundaries(str(case["text"])) == case["text"]


@pytest.mark.parametrize("case", PRICES, ids=PRICE_IDS)
def test_display_dollars_inline_reader_finds_no_maths_in_a_price(case: dict[str, object]) -> None:
    # "Burmese, $-$$" drew "-$": `$-$` paired as maths and left one dollar (2026-11-27).
    text = str(case["text"])
    assert [i for i in range(len(text)) if maths_pair_end(text, i) is not None] == []


@pytest.mark.parametrize("case", PRICES, ids=PRICE_IDS)
def test_display_dollars_calculation_layout_leaves_a_price(case: dict[str, object]) -> None:
    assert layout_calculations(str(case["text"])) == case["text"]


def test_display_dollars_calculation_layout_splits_no_chain_a_tier_closes() -> None:
    # Paired with the first two dollars of "$$$", this chain was laid out in rows.
    assert layout_calculations("$$x = 1 + 1 = 2$$$") == "$$x = 1 + 1 = 2$$$"
    assert layout_calculations("Then $$x = 1 + 1 = 2$$.") == "Then\n$$x = 1 + 1$$  \n$$x = 2$$."


def test_display_dollars_notation_between_tiers_paragraphs_apart() -> None:
    text = "Zuni - $$.\n\nIts smell is CC(=O)O.\n\nTartine - $$."
    assert "`CC(=O)O`" in code_notation(text)
