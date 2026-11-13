r"""Worked blocks from the 2026-11-12 comparison of six models on 50 questions in parts, laid
out as the phone shows them.

Qwen wrote word symbols in a word group with the underscore escaped for text mode
(``\text{white\_pigment} = 3 \times 4``), the layout braced the subscript after it, and
the phone drew "white_{pigment}" as source; its Given, Required and Answer lines wrote the
same symbol as ``white_{pigment}``, the subscript it is. GPT-6 Luna wrote its working's unit after the
number (``L = 8 gal``), which maths draws as 8 times g, a and l in italic ("8gal"), while
the answer lines of the same reply set ``8\,\mathrm{gal}``. Each block below is the kind
the model wrote, look-alikes beside it.
"""

from __future__ import annotations

import itertools

import pytest

from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.worked_render import WorkedLayout
from app.modules.chat.worked_stream import ReplyFilter, WorkedFilter
from app.modules.chat.worked_text import tidy_symbol, tidy_tex
from app.modules.chat.worked_units import declared_units, units_upright
from app.tests.behavior.latex_check import latex_problems

OTHER = WorkedLayout()

PAINTER = r"""```worked
given: \text{total\_paint} | 28 | gallons | total paint
given: \text{ratio\_total} | 3 + 2 + 1 + 1 | | total parts in the ratio
required: \text{white\_pigment} | gallons of white pigment
required: linseed_oil | gallons of linseed oil
part: a | Gallons of white pigment
formula: Gallon per part | \text{gallons per part} = \frac{\text{total\_paint}}{\text{ratio\_total}}
substitution: \text{gallons per part} = \frac{28}{7}
substitution: \text{white\_pigment} = 3 \times 4
answer: \text{white\_pigment} | 12 | gallons
part: b | Gallons of linseed oil
substitution: \text{linseed\_{oil}} = 2 \times 4
answer: linseed_oil | 8 | gallons
```"""
RATIO = r"""```worked
given: V | 28 | gal | total paint
given: r | 3:2:1:1 | | ratio of white pigment, linseed oil, dryer, and turpentine
required: W | white pigment
required: T | turpentine
part: a | White pigment
formula: Ratio share | W = V \times \frac{3}{7}
substitution: W = 28 × 3 ÷ (3 + 2 + 1 + 1)
substitution: W = 12 gal
answer: W | 12 | gal
part: b | Turpentine
substitution: T = 28 × 1 ÷ (3 + 2 + 1 + 1)
substitution: T = 4gal
substitution: 12 + 8 + 4 + 4 = 28 gal
answer: T | 4 | gal
```"""
# Ages: the unknown is s, the years are a unit word, and "4s" is 4 times s.
AGES = r"""```worked
given: f | 4s | years | father's age now
given: t | 20 | years | years from now
required: s | son's age now
formula: Ages in 20 years | 4s + 20 = 2(s + 20)
step: 4s + 20 = 2s + 40 | expand the brackets
step: 2s = 20 | subtract 2s and 20
substitution: s = 10 years
substitution: f = 4 \times 10 = 40 years
answer: s | 10 | years
```"""
# Hours: "3h" in the working is 3 times h, and h is no unit the block names.
HEIGHT = r"""```worked
given: s | 3h | m | side, three times the height
given: A | 54 | cm^2 | area
required: h | height
formula: Area | A = s h
substitution: 54 = 3h \times h
substitution: h = 3\,\mathrm{cm}
answer: h | 3 | cm
```"""
# An answer in a unit no given names, after the working that uses it (local review,
# 2026-11-12): the working drawn before the answer arrives must stay as it was drawn.
RATE = r"""```worked
given: v | 60 | km/h | speed
given: t | 2 | h | time
required: d | distance
formula: Distance | d = v \times t
substitution: d = 60 \times 2 = 120 km
answer: d | 120 | km
```
So the car covers 120 km in two hours."""
COST = r"""```worked
given: V | 28 | gal | total paint
required: W | white pigment
required: c | cost
required: c | cost again
part: a | White pigment
substitution: W = 12 gal
answer: W | 12 | gal
part: b | Cost
substitution: c = 12 \times 30 = 360 Birr
answer: c | 360 | Birr
part: c | Cost again
substitution: c = 2 \times 180 = 360 Birr
answer: c | 360 | Birr
```"""
BLOCKS = {
    "painter": PAINTER,
    "ratio": RATIO,
    "ages": AGES,
    "height": HEIGHT,
    "rate": RATE,
    "cost": COST,
}


def _laid_out(block: str) -> str:
    worked = WorkedFilter(OTHER)
    worked.feed(block)
    worked.close()
    return worked.text


@pytest.mark.parametrize(("name", "block"), BLOCKS.items())
def test_no_line_of_these_blocks_shows_latex_source(name: str, block: str) -> None:
    assert latex_problems(_laid_out(block)) == [], name


@pytest.mark.parametrize(
    ("tex", "tidy"),
    [
        # The underscore escaped for text mode joins a word symbol to its subscript: the
        # symbol is written as the symbol fields write ``white_pigment``.
        (r"\text{white\_pigment} = 3 \times 4", r"white_{pigment} = 3 \times 4"),
        (r"\text{white\_{pigment}}", r"white_{pigment}"),
        # An upright group other than \text keeps its letters upright.
        (r"\mathrm{v\_max}", r"\mathrm{v}_{\mathrm{max}}"),
        (
            r"\frac{\text{total\_paint}}{\text{ratio\_total}}",
            r"\frac{total_{paint}}{ratio_{total}}",
        ),
        # Words around it stay upright words; several joined words are the subscript's.
        (r"\text{mass\_of\_salt}", r"\text{mass}_{\text{of salt}}"),
        (r"\text{cost\_per item}", r"\text{cost}_{\text{per}}\text{ item}"),
        (r"\text{total white\_pigment}", r"\text{total white}_{\text{pigment}}"),
        # A second subscript straight after the first is more of it: one base, one script.
        (r"\text{rate\_{in}\_{out}}", r"\text{rate}_{\text{in out}}"),
        # A formula's count is the digits alone, its letters upright (local review).
        (r"\text{H\_2O}", r"\text{H}_{2}\text{O}"),
        (r"\mathrm{H\_2O}", r"\mathrm{H}_{2}\mathrm{O}"),
        (r"\mathrm{CO\_2}", r"\mathrm{CO}_{2}"),
        (r"\text{v\_1}", r"\text{v}_{1}"),
        # TeX reads ``H_2O`` as H, subscript 2, then O; a subscript of letters or digits alone
        # is braced.
        ("H_2O", "H_2O"),
        (r"\mathrm{H_2O}", r"\mathrm{H_2O}"),
        ("x_2y", "x_2y"),
        ("v_12", "v_{12}"),
        # Bare in maths it is the script the symbol fields write.
        (r"white\_pigment = 12", r"white_{pigment} = 12"),
        ("white_pigment", "white_{pigment}"),
        # Look-alikes: a blank, an underscore before a space, words, scripts already set.
        (r"x = \_\_", r"x = \_\_"),
        (r"\text{a\_ b}", r"\text{a\_ b}"),
        (r"\text{gallons per part} = 4", r"\text{gallons per part} = 4"),
        (r"v_{max} = 3", r"v_{max} = 3"),
        (r"x_1 + x_2", r"x_1 + x_2"),
        (r"t_{\text{top}}", r"t_{\text{top}}"),
        (r"\text{abc", r"\text{abc"),
    ],
)
def test_a_word_symbols_escaped_subscript_is_a_subscript(tex: str, tidy: str) -> None:
    assert tidy_tex(tex) == tidy


def test_a_word_symbol_is_one_subscript_in_every_line() -> None:
    """Given, the where-line, Required, the working and the answer all write the symbol
    with its subscript, one spelling however the model wrote it; no line keeps the escaped
    underscore."""
    laid_out = _laid_out(PAINTER)
    assert "\\_" not in laid_out
    assert "(a) $white_{pigment}$ (gallons of white pigment)" in laid_out
    assert "(b) $linseed_{oil}$ (gallons of linseed oil)" in laid_out
    assert "$white_{pigment} = 3 \\times 4$" in laid_out
    assert "$white_{pigment} = 12\\,\\mathrm{gallons}$" in laid_out
    assert "$linseed_{oil} = 2 \\times 4$" in laid_out
    assert "$linseed_{oil} = 8\\,\\mathrm{gallons}$" in laid_out
    assert "$total_{paint} = 28\\,\\mathrm{gallons}$" in laid_out
    assert "where $total_{paint}$ = total paint" in laid_out
    assert r"\frac{total_{paint}}{ratio_{total}}" in laid_out
    assert tidy_symbol(r"\text{white\_pigment}") == tidy_symbol("white_pigment")


@pytest.mark.parametrize(
    ("block", "row"),
    [
        (RATIO, r"$W = 12\,\mathrm{gal}$"),
        (RATIO, r"$T = 4\,\mathrm{gal}$"),
        (RATIO, r"$12 + 8 + 4 + 4 = 28\,\mathrm{gal}$"),
        (AGES, r"$s = 10\,\mathrm{years}$"),
        (AGES, r"$f = 4 \times 10 = 40\,\mathrm{years}$"),
        # Look-alikes: a letter after a number is a symbol, not a unit.
        # A unit named only by a record after the line: the line stays as it was drawn.
        (RATE, r"$d = 60 \times 2 = 120 km$"),
        (COST, r"$c = 12 \times 30 = 360 Birr$"),
        # A unit an earlier part's answer named.
        (COST, r"$c = 2 \times 180 = 360\,\mathrm{Birr}$"),
        (AGES, "$4s + 20 = 2(s + 20)$"),
        (AGES, "$2s = 20$"),
        (HEIGHT, r"$54 = 3h \times h$"),
    ],
)
def test_a_unit_in_the_working_is_set_as_the_answer_sets_it(block: str, row: str) -> None:
    # A line of the working, under its heading or the line before it (the answer line of
    # the same value follows a blank line).
    assert f"  \n{row}" in _laid_out(block)


@pytest.mark.parametrize(
    ("fields", "units"),
    [
        (["gal", "gal"], ("gals", "gal")),
        (["years"], ("years", "year")),
        (["Birr"], ("Birrs", "Birr")),
        (["km/h", r"\text{min}"], ("km/h", "mins", "min")),
        # One letter may be a symbol; no unit at all is none.
        (["s", "h", "m/s", "N", "m^2"], ()),
        (["", "—", "none", "n/a"], ()),
        # "ms" is a unit of its own, never "m" plural.
        (["ms"], ("ms",)),
    ],
)
def test_declared_units_are_the_records_unit_words(
    fields: list[str], units: tuple[str, ...]
) -> None:
    assert declared_units(fields) == units


@pytest.mark.parametrize(
    ("tex", "shown"),
    [
        ("L = 8 gal", r"L = 8\,\mathrm{gal}"),
        ("T = 4gal", r"T = 4\,\mathrm{gal}"),
        (r"x = 28\ gal", r"x = 28\,\mathrm{gal}"),
        ("P = 1{,}200 Birr + 3", r"P = 1{,}200\,\mathrm{Birr} + 3"),
        # Already upright, or no unit that ends a value.
        (r"V = 28\,\mathrm{gal}", r"V = 28\,\mathrm{gal}"),
        (r"\text{for 2 gal} = 2 gal", r"\text{for 2 gal} = 2\,\mathrm{gal}"),
        ("x = 2 galx", "x = 2 galx"),
        ("x = 2 gal^2", "x = 2 gal^2"),
        ("v = 5 gal/h", "v = 5 gal/h"),
        ("v_2 gal", "v_2 gal"),
        ("x = 5 gallons", "x = 5 gallons"),
    ],
)
def test_units_upright_sets_a_unit_only_where_it_ends_a_value(tex: str, shown: str) -> None:
    assert units_upright(tex, declared_units(["gal", "Birr"])) == shown


def test_a_sentence_in_the_working_stays_words() -> None:
    block = (
        "```worked\ngiven: A | 60 | hectares | farm\nrequired: W | wheat\n"
        "substitution: Wheat gets 5 parts\nsubstitution: W = 25 hectares\n"
        "answer: W | 25 | hectares\n```"
    )
    laid_out = _laid_out(block)
    assert "Wheat gets 5 parts" in laid_out
    assert "$Wheat" not in laid_out
    assert r"$W = 25\,\mathrm{hectares}$" in laid_out


@pytest.mark.parametrize("block", BLOCKS.values())
def test_these_blocks_stream_without_a_rewrite(block: str) -> None:
    accum = StreamAccum()
    reply_filter = ReplyFilter(accum, OTHER)
    seen: list[str] = []
    for start in range(0, len(block), 7):
        if sent := reply_filter.feed(block[start : start + 7]):
            accum.shown.append(sent)
        seen.append("".join(accum.shown))
    if tail := reply_filter.flush():
        accum.shown.append(tail)
    assert not accum.rewritten
    for earlier, later in itertools.pairwise(seen):
        assert later.startswith(earlier)
    assert "".join(accum.shown).strip() == _laid_out(block).strip()
