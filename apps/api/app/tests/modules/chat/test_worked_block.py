"""A ```worked block: its records read and validated, laid out as a verified reply, and
streamed as the layout, never as records."""

from __future__ import annotations

import itertools

import pytest

from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.worked_render import WorkedLayout, render_worked
from app.modules.chat.worked_solution import (
    Answer,
    Formula,
    Given,
    PartLabel,
    Required,
    Step,
    WorkedSolution,
    assemble,
    read_record,
)
from app.modules.chat.worked_stream import ReplyFilter, WorkedFilter
from app.modules.chat.worked_units import currency_first, unit_tex
from app.tests.behavior.latex_check import latex_problems

PHYSICS = WorkedLayout(law_heading=True)
OTHER = WorkedLayout()

DISPLACEMENT = r"""```worked
given: v | 20 | m/s | speed
given: t | 120 | s | time
required: s | displacement
formula: Constant velocity | s = v t
substitution: s = 20 \times 120
substitution: s = 2400\,\mathrm{m}
answer: s | 2400 | m | east
```"""

DISPLACEMENT_LAID_OUT = (
    "**Given**  \n$v = 20\\,\\mathrm{m/s}$  \n$t = 120\\,\\mathrm{s}$  \n"
    "where $v$ = speed, $t$ = time\n\n"
    "**Required**  \n$s$ (displacement)\n\n"
    "**Solution**\n\n"
    "**Constant velocity formula**  \n$s = v t$\n\n"
    "**Substitution**  \n$s = 20 \\times 120$  \n$s = 2400\\,\\mathrm{m}$\n\n"
    "**Answer**\n\n$2400\\,\\mathrm{m}$ (east)"
)

POLES = r"""Here is the conversion.

```worked
given: d | 100 | m | distance between the poles
required: d_{cm} | distance in centimetres
required: d_{km} | distance in kilometres
part: a | Distance in centimetres
formula: Conversion | 1\,\mathrm{m} = 100\,\mathrm{cm}
substitution: d_{cm} = 100 \times 100 = 10000\,\mathrm{cm}
answer: d_{cm} | 10000 | cm
part: b | Distance in kilometres
formula: Conversion | 1\,\mathrm{km} = 1000\,\mathrm{m}
substitution: d_{km} = \frac{100}{1000} = 0.1\,\mathrm{km}
answer: d_{km} | 0.1 | km
```
"""


@pytest.mark.parametrize(
    ("line", "record"),
    [
        ("given: v | 20 | m/s | speed", Given(symbol="v", value="20", unit="m/s", meaning="speed")),
        ("given: v = 20 | m/s | speed", Given(symbol="v", value="20", unit="m/s", meaning="speed")),
        ("- given: $m_1$ | $1$ | kg", Given(symbol="m_1", value="1", unit="kg")),
        (
            r"given: t | 40 | min | time | 2400\,\mathrm{s}",
            Given(
                symbol="t", value="40", unit="min", meaning="time", converted=r"2400\,\mathrm{s}"
            ),
        ),
        # A quantity the question gives as a letter: a given with no value (2026-11-11).
        ("given: M | | | mass of the rod", Given(symbol="M", meaning="mass of the rod")),
        ("given: v", Given(symbol="v")),
        ("Required: s | displacement", Required(symbol="s", meaning="displacement")),
        ("formula: Ohm's law | V = IR", Formula(name="Ohm's law", tex="V = IR")),
        ("formula: V = IR", Formula(tex="V = IR")),
        (
            r"solve_for: t | t = \frac{d}{v}",
            Step(kind="solve_for", symbol="t", tex=r"t = \frac{d}{v}"),
        ),
        ("step: 2x = 8 | subtract 3", Step(kind="step", tex="2x = 8", move="subtract 3")),
        (r"substitution: $s = 20 \times 120$", Step(kind="substitution", tex=r"s = 20 \times 120")),
        (
            "answer: s | 2400 | m | due East",
            Answer(symbol="s", value="2400", unit="m", note="due East"),
        ),
        ("answer: x = 3", Answer(symbol="x", value="3")),
        ("answer: 15", Answer(value="15")),
        ("part: (b) | Speed", PartLabel(letter="(b)", title="Speed")),
    ],
)
def test_read_record_validates_each_kind(line: str, record: object) -> None:
    assert read_record(line) == record


@pytest.mark.parametrize(
    "line",
    [
        "",
        "The answer is 2400 m.",
        "given:",
        "answer: s |",  # no value
        "formula: Name |",
        "note: something",
        "substitution: ```",
        "given: " + "x" * 400 + " | 1",
    ],
)
def test_read_record_leaves_out_what_is_no_record(line: str) -> None:
    assert read_record(line) is None


def _solution(block: str) -> WorkedSolution:
    records = [read_record(line) for line in block.split("\n")]
    return assemble([record for record in records if record is not None])


def test_render_lays_physics_out_as_its_verified_replies() -> None:
    assert render_worked(_solution(DISPLACEMENT), PHYSICS) == DISPLACEMENT_LAID_OUT


def test_render_heads_the_formula_with_its_name_and_keeps_the_symbol_elsewhere() -> None:
    laid_out = render_worked(_solution(DISPLACEMENT), OTHER)
    # The name heads the formula ("<name> formula"), never a note beside it.
    assert "**Constant velocity formula**  \n$s = v t$\n" in laid_out
    assert "— Constant velocity" not in laid_out
    assert laid_out.endswith("**Answer**\n\n$s = 2400\\,\\mathrm{m}$ (east)")


def test_render_puts_a_rearrangement_under_its_formula_and_moves_under_steps() -> None:
    rearranged = _solution(
        "given: d | 100 | m\ngiven: v | 5 | m/s\nrequired: t\nformula: Speed | v = \\frac{d}{t}\n"
        "solve_for: t | t = \\frac{d}{v}\nsubstitution: t = \\frac{100}{5}\nanswer: t | 20 | s"
    )
    assert "**Speed formula**  \n$v = \\frac{d}{t}$  \nSolve for $t$  \n$t = \\frac{d}{v}$" in (
        render_worked(rearranged, OTHER)
    )
    moves = _solution("step: 2x + 3 = 11 | given\nstep: 2x = 8 | subtract 3\nanswer: x | 4")
    assert render_worked(moves, OTHER) == (
        "**Steps**  \n$2x + 3 = 11$ — given  \n$2x = 8$ — subtract 3\n\n**Answer**\n\n$x = 4$"
    )


def test_render_lays_a_question_in_parts_out_part_by_part() -> None:
    laid_out = render_worked(_solution(POLES), OTHER)
    assert laid_out.startswith("**Given**  \n$d = 100\\,\\mathrm{m}$")
    # One Required naming what each part finds, then Solution, then the parts.
    assert (
        "**Required**  \n(a) $d_{cm}$ (distance in centimetres)  \n"
        "(b) $d_{km}$ (distance in kilometres)\n\n**Solution**\n\n**(a) Distance" in laid_out
    )
    assert "**(a) Distance in centimetres**\n\n**Conversion formula**" in laid_out
    assert "**Answer (a)**\n\n$d_{cm} = 10000\\,\\mathrm{cm}$\n\n---\n\n**(b) Distance" in laid_out
    assert laid_out.endswith("**Answer (b)**\n\n$d_{km} = 0.10\\,\\mathrm{km}$")


def test_render_writes_no_answer_heading_without_an_answer() -> None:
    cut = _solution("given: v | 20 | m/s\nformula: Speed | v = d/t")
    assert "**Answer**" not in render_worked(cut, PHYSICS)


@pytest.mark.parametrize(
    ("unit", "tex"),
    [
        ("", ""),
        ("m/s", r"\,\mathrm{m/s}"),
        ("m/s^2", r"\,\mathrm{m/s²}"),
        ("kg*m", r"\,\mathrm{kg·m}"),
        (r"\text{km}", r"\,\mathrm{km}"),
        ("°C", r"\,^\circ\mathrm{C}"),
        ("°", r"^\circ"),
        ("%", r"\,\%"),
        (r"\Omega", r"\,\Omega"),
        # A unit in words is text: \mathrm ran "square units" together (2026-11-16).
        ("square units", r"\,\text{square units}"),
        (r"\mathrm{cubic units}", r"\,\text{cubic units}"),
    ],
)
def test_unit_tex_writes_units_upright(unit: str, tex: str) -> None:
    assert unit_tex(unit) == tex


@pytest.mark.parametrize(
    ("tex", "expected"),
    [
        # A unit field laid after the value (``unit_tex``).
        (r"0.90\,\mathrm{\$}", r"\$0.90"),
        (r"0.15\,\mathrm{\$/kWh}", r"\$0.15\mathrm{/kWh}"),
        (r"-3\,\mathrm{€}", r"-\mathrm{€}3"),
        (r"1{,}200\,\mathrm{£}", r"\mathrm{£}1{,}200"),
        (r"500\,\mathrm{¥}", r"\mathrm{¥}500"),
        # The model's own LaTeX in a substitution line.
        (r"C = 2 \times 3 \times 0.15 = 0.90\,\$", r"C = 2 \times 3 \times 0.15 = \$0.90"),
        (r"C = 0.9 \text{ €}", r"C = \mathrm{€}0.9"),
        # Already before the number, a cent sign, a currency in letters, and no currency.
        (r"C = \$0.90", r"C = \$0.90"),
        (r"15\,\mathrm{¢/kWh}", r"15\,\mathrm{¢/kWh}"),
        (r"12\,\mathrm{USD}", r"12\,\mathrm{USD}"),
        (r"x = 5 + 3", r"x = 5 + 3"),
        (r"T = 5\,^\circ\mathrm{C}", r"T = 5\,^\circ\mathrm{C}"),
        (r"v_1 = 3\,\mathrm{m/s}", r"v_1 = 3\,\mathrm{m/s}"),
        # A list: the sign belongs to the next item, not to "5," (review of #2300).
        (r"x = 5, \$3", r"x = 5, \$3"),
        (r"(1, €3)", r"(1, €3)"),
        (r"1.5. \$2", r"1.5. \$2"),
    ],
)
def test_currency_first_writes_a_currency_sign_before_its_number(tex: str, expected: str) -> None:
    assert currency_first(tex) == expected


def test_a_cost_answer_shows_the_currency_before_the_value() -> None:
    """Live (2026-11-05): a 2000 W heater for 3 h at 15¢/kWh got the card ``0.90 $``."""
    block = _solution(
        "given: P | 2000 | W | power | 2\\,\\mathrm{kW}\n"
        "given: r | 0.15 | $/kWh | price\n"
        "required: C | cost\n"
        "formula: Cost | C = P t r\n"
        "substitution: C = 2 \\times 3 \\times 0.15 = 0.90\\,\\$\n"
        "answer: C | 0.90 | $"
    )
    laid_out = render_worked(block, OTHER)
    assert r"$r = \$0.15\mathrm{/kWh}$" in laid_out
    assert r"$C = 2 \times 3 \times 0.15 = \$0.90$" in laid_out
    assert laid_out.endswith(r"$C = \$0.90$")
    assert latex_problems(laid_out) == []


def _stream(
    reply: str, size: int, layout: WorkedLayout | None = PHYSICS
) -> tuple[str, list[str], StreamAccum]:
    """``reply`` through a ReplyFilter in chunks of ``size``: the text the client was sent,
    the text after each chunk, and the accumulator the stream path appends to."""
    accum = StreamAccum()
    reply_filter = ReplyFilter(accum, layout)
    seen: list[str] = []
    for start in range(0, len(reply), size):
        if sent := reply_filter.feed(reply[start : start + size]):
            accum.shown.append(sent)
        seen.append("".join(accum.shown))
    if tail := reply_filter.flush():
        accum.shown.append(tail)
    return "".join(accum.shown), seen, accum


@pytest.mark.parametrize("size", [1, 2, 3, 7, 40, 10_000])
def test_a_block_streams_as_its_layout_at_any_chunk_size(size: int) -> None:
    sent, seen, accum = _stream(DISPLACEMENT, size)
    assert sent.strip() == DISPLACEMENT_LAID_OUT
    assert not accum.rewritten
    # What the phone was sent only ever grows, and it never shows a record.
    for earlier, later in itertools.pairwise(seen):
        assert later.startswith(earlier)
    assert all("given:" not in text and "```" not in text for text in seen)


def test_a_block_streams_section_by_section() -> None:
    _sent, seen, _accum = _stream(DISPLACEMENT, 5)
    assert any(text.startswith("**Given**") and "**Required**" not in text for text in seen)
    assert any("**Required**" in text and "**Substitution**" not in text for text in seen)


@pytest.mark.parametrize("size", [1, 4, 10_000])
def test_text_around_a_block_passes_through(size: int) -> None:
    sent, _seen, accum = _stream(POLES + "\nThe poles are far apart.", size, OTHER)
    assert sent.startswith("Here is the conversion.\n\n**Given**")
    assert sent.rstrip().endswith("$d_{km} = 0.10\\,\\mathrm{km}$\n\n\nThe poles are far apart.")
    assert not accum.rewritten


@pytest.mark.parametrize(
    "reply",
    [
        "Plain prose with no block.\n\n**Answer**\n\n$x = 4$",
        "```python\nprint(1)\n```",
        "    ```worked\nindented four spaces is code",
        "Some text ```worked on the same line",
    ],
)
def test_a_reply_without_a_block_is_unchanged(reply: str) -> None:
    sent, _seen, accum = _stream(reply, 3)
    assert sent == reply
    assert not accum.rewritten


def test_without_a_layout_the_filter_only_strips_scaffolding() -> None:
    sent, _seen, _accum = _stream(DISPLACEMENT, 4, None)
    assert sent == DISPLACEMENT


def test_a_block_of_no_records_is_shown_as_written() -> None:
    reply = "```worked\n**Given:** v = 20 m/s\n**Answer:** 2400 m\n```"
    sent, _seen, _accum = _stream(reply, 5)
    assert sent.strip() == "**Given:** v = 20 m/s\n**Answer:** 2400 m"


def test_a_block_cut_off_by_the_stream_end_is_laid_out_as_far_as_it_went() -> None:
    cut = DISPLACEMENT.split("substitution:")[0]
    sent, _seen, _accum = _stream(cut, 6)
    assert sent.strip().endswith("**Constant velocity formula**  \n$s = v t$")
    assert "**Answer**" not in sent


def test_a_record_out_of_order_rewrites_the_reply_and_marks_it() -> None:
    late_given = DISPLACEMENT.removesuffix("```") + "given: m | 5 | kg | mass\n```"
    sent, _seen, accum = _stream(late_given, 3)
    assert accum.rewritten
    assert sent.startswith(
        "**Given**  \n$v = 20\\,\\mathrm{m/s}$  \n$t = 120\\,\\mathrm{s}$  \n$m = 5"
    )
    assert sent.rstrip().endswith("$2400\\,\\mathrm{m}$ (east)")


def test_the_worked_filter_counts_the_blocks_it_laid_out() -> None:
    worked = WorkedFilter(PHYSICS)
    worked.feed(DISPLACEMENT + "\n\n" + DISPLACEMENT)
    worked.close()
    assert worked.blocks == 2
    assert worked.text.count("**Given**") == 2


def test_render_tidies_the_models_tex_and_drops_a_conversion_to_itself() -> None:
    beam = _solution(
        "given: m1 | 1 | kg | first mass | 1000\\,\\mathrm{g}\n"
        "given: m2 | 500 | g | second mass | 500\\,\\mathrm{g}\n"
        "required: M | mass on the other side\n"
        "formula: Balance | M = m_1 + m_2\n"
        "substitution: M = 1000 + 500 = 1500\\,\\mathrm{g}\n"
        "answer: M | 1500 | g"
    )
    laid_out = render_worked(beam, OTHER)
    assert "$m_1 = 1\\,\\mathrm{kg} = 1000\\,\\mathrm{g}$" in laid_out
    assert "$m_2 = 500\\,\\mathrm{g}$  \n" in laid_out  # never "500 g = 500 g"
    displacement = _solution("formula: Displacement | \\Delta x = x_final - x_initial\nanswer: 1")
    assert "x_{final} - x_{initial}" in render_worked(displacement, OTHER)


def test_render_keeps_one_part_when_the_model_names_it_twice() -> None:
    poles = _solution(
        "given: d | 100 | m | distance\nrequired: a. length in cm, b. length in km\n"
        "part: a | In centimetres\nformula: Unit conversion | 1\\,\\mathrm{m} = 100\\,\\mathrm{cm}\n"
        "part: a\nsubstitution: d = 100 \\times 100\nanswer: cm | 10000 | cm\n"
        "part: b | In kilometres\nsubstitution: d = 100 \\div 1000\nanswer: d | 0.1 | km"
    )
    laid_out = render_worked(poles, OTHER)
    assert laid_out.count("**(a)") == 1 and laid_out.count("---") == 1
    # One record for both parts, its symbol in words: each part is asked on its own
    # lettered line, by its title; a symbol that repeats the unit names nothing.
    assert "**Required**  \n(a) In centimetres  \n(b) $d$ (In kilometres)\n" in laid_out
    assert "**Answer (a)**\n\n$10000\\,\\mathrm{cm}$" in laid_out


def test_render_writes_a_sentence_in_a_maths_field_as_text() -> None:
    azeb = _solution(
        "formula: Displacement | \\Delta x = x_C - x_A\n"
        "step: Let A be the origin and the direction from A to B positive | set up\n"
        "substitution: \\Delta x = 100 - 0\nanswer: \\Delta x | 100 | m"
    )
    laid_out = render_worked(azeb, OTHER)
    assert "\nLet A be the origin and the direction from A to B positive — set up" in laid_out
    assert "$Let" not in laid_out


@pytest.mark.parametrize(
    ("symbol", "words"),
    [("a) in cm, b) in km", True), ("length in cm", True), ("\\Delta x", False), ("v_i", False)],
)
def test_a_symbol_in_words_is_text(symbol: str, words: bool) -> None:
    from app.modules.chat.worked_text import names_nothing

    assert names_nothing(symbol) is words


def test_moves_then_a_substitution_stay_in_the_order_written() -> None:
    block = "```worked\nstep: 2x + 3 = 11 | given\nstep: 2x = 8 | subtract 3\nsubstitution: x = 8 / 2\nanswer: x | 4\n```"
    sent, _seen, accum = _stream(block, 4, OTHER)
    assert not accum.rewritten
    assert sent.strip().startswith(
        "**Steps**  \n$2x + 3 = 11$ — given  \n$2x = 8$ — subtract 3  \n$x = 8 / 2$"
    )
    assert "**Substitution**" not in sent


def test_a_formula_before_the_first_part_label_is_that_parts() -> None:
    block = _solution(
        "given: d | 100 | m\nformula: Speed | v = d/t\npart: a | speed\nsubstitution: v = 100/5\n"
        "answer: v | 20 | m/s\npart: b | time\nsubstitution: t = 100/20\nanswer: t | 5 | s"
    )
    laid_out = render_worked(block, OTHER)
    assert laid_out.count("**(a)") == 1 and laid_out.count("---") == 1
    assert "**(a) Speed**\n\n**Speed formula**  \n$v = d/t$\n" in laid_out


def test_a_rewrite_keeps_the_list_length_and_a_stop_after_it_keeps_the_reply_whole() -> None:
    accum = StreamAccum()
    accum.shown.append("Before.\n\n")
    reply_filter = ReplyFilter(accum, PHYSICS)
    late = DISPLACEMENT.removesuffix("```") + "given: m | 5 | kg | mass\n```"
    for start in range(0, len(late), 3):
        if sent := reply_filter.feed(late[start : start + 3]):
            accum.shown.append(sent)
    if tail := reply_filter.flush():
        accum.shown.append(tail)
    assert accum.rewritten and accum.shown[0] == "Before.\n\n"
    accum.mark_user_stop()
    # The client's count is of the text it drew before the rewrite: never cut by it.
    assert accum.reply_text(client_shown_chars=20).endswith("$2400\\,\\mathrm{m}$ (east)")


def test_the_closer_of_a_block_cut_at_the_cap_is_dropped() -> None:
    from app.modules.chat.worked_stream import MAX_BLOCK_CHARS

    filler = "".join(f"substitution: x = {n}\n" for n in range(MAX_BLOCK_CHARS // 15))
    worked = WorkedFilter(OTHER)
    worked.feed(f"```worked\ngiven: x | 1\n{filler}```\n\nAfter the block.")
    worked.close()
    assert "```" not in worked.text
    assert worked.text.rstrip().endswith("After the block.")


@pytest.mark.parametrize(
    "tex",
    ["x_{final} = x_{initial} + v_{avg} t", "v_{avg} = \\frac{distance}{time}"],
)
def test_a_line_with_latex_is_maths_however_many_words_it_holds(tex: str) -> None:
    block = _solution(f"substitution: {tex}\nstep: {tex} | carried on\nanswer: x | 1")
    laid_out = render_worked(block, OTHER)
    assert laid_out.count(f"${tex}$") == 2


# Words in a maths field, a sentence as a step, and a symbol in words, as a model wrote them.
SLOPPY = (
    "```worked\ngiven: d_AB | 300 | m | distance\nrequired: a) in cm, b) in km\n"
    "formula: Displacement | \\Delta x = x_final - x_initial\n"
    "step: Let A be the origin and the direction from A to B positive | set up\n"
    "substitution: v_{avg} = \\frac{distance}{time}\nanswer: \\Delta x | 100 | m | east\n```"
)


@pytest.mark.parametrize("block", [DISPLACEMENT, POLES, SLOPPY])
def test_no_laid_out_block_shows_latex_source(block: str) -> None:
    worked = WorkedFilter(OTHER)
    worked.feed(block)
    worked.close()
    assert latex_problems(worked.text) == []


@pytest.mark.parametrize(
    ("line", "record"),
    [
        # Grade 12 run (2026-11-13): \ln|x| was split at its bars, the card ended at \ln.
        (
            r"answer: \int f(x)\,dx | \frac{3}{4}x^{4/3} - \frac{1}{2}\ln|x| + C | | indefinite integral",
            Answer(
                symbol=r"\int f(x)\,dx",
                value=r"\frac{3}{4}x^{4/3} - \frac{1}{2}\ln|x| + C",
                note="indefinite integral",
            ),
        ),
        # The given's value held |x - 5|: Given read "f(x) = {x = | function".
        (
            r"given: f(x) | \frac{x|x-5|}{x^2-25} | | function",
            Given(symbol="f(x)", value=r"\frac{x|x-5|}{x^2-25}", meaning="function"),
        ),
        (r"given: d = |x_2 - x_1| | m | distance", Given(symbol="d", value="|x_2 - x_1|", unit="m", meaning="distance")),
        ("answer: P(A|B) | 0.4", Answer(symbol="P(A|B)", value="0.4")),
        (r"answer: \lvert v \rvert | 5 | m/s", Answer(symbol=r"\lvert v \rvert", value="5", unit="m/s")),
        # A field of nothing but bars is empty: "(|)" stood after the card's value.
        (r"answer: L | \frac{1}{5} | | |", Answer(symbol="L", value=r"\frac{1}{5}")),
        # A record that spaces none of its bars still splits at each.
        ("answer: v|3.33|m/s", Answer(symbol="v", value="3.33", unit="m/s")),
        ("given: v|20|m/s|speed", Given(symbol="v", value="20", unit="m/s", meaning="speed")),
        # "||" for an empty field, and separators spaced on one side (review, 2026-11-13).
        ("given: n | 2 || amount of substance", Given(symbol="n", value="2", meaning="amount of substance")),
        ("answer: n | 4 || to 3 s.f.", Answer(symbol="n", value="4", note="to 3 s.f.")),
        ("answer: x | 5 ||", Answer(symbol="x", value="5")),
        (r"given: m | 2 | kg || 2000\,\mathrm{g}", Given(symbol="m", value="2", unit="kg", converted=r"2000\,\mathrm{g}")),
        ("answer: v |3.33 | m/s", Answer(symbol="v", value="3.33", unit="m/s")),
        ("answer: v | 3.33|m/s", Answer(symbol="v", value="3.33", unit="m/s")),
        ("given: v = 20|m/s | speed", Given(symbol="v", value="20", unit="m/s", meaning="speed")),
        # A value that is all absolute value, and maths bars inside brackets.
        ("answer: |-5|", Answer(value="|-5|")),
        (r"answer: S | \{x | x > 0\}", Answer(symbol="S", value=r"\{x | x > 0\}")),
        ("answer: p | P(A | B) = 0.4", Answer(symbol="p", value="P(A | B) = 0.4")),
    ],
)  # fmt: skip
def test_a_bar_inside_the_maths_is_no_field_separator(line: str, record: object) -> None:
    assert read_record(line) == record


def test_a_part_s_own_letter_is_not_said_twice() -> None:
    """The layout letters each part: "(a) $t$ (time in the air (a))" said it twice (phys30)."""
    solution = _solution(
        "required: t | time in the air (a)\nrequired: d | distance along the slope (b)\n"
        "part: a | Time in the air (a)\nanswer: t | 1.63 | s\n"
        "part: b | Distance along the slope (b)\nanswer: d | 16.7 | m"
    )
    assert [ask.meaning for ask in solution.required] == [
        "time in the air",
        "distance along the slope",
    ]
    assert [part.title for part in solution.parts] == [
        "Time in the air",
        "Distance along the slope",
    ]


def test_another_letter_in_an_ask_is_the_question_s_own() -> None:
    """Review of phys30: "force on block (a)" lost its block's letter. Only an ask's own
    part letter goes, and only in a question in parts."""
    alone = _solution("required: F | force on block (a)\nanswer: F | 3 | N")
    assert alone.required[0].meaning == "force on block (a)"
    parts = _solution(
        "required: F | force on block (b)\nrequired: T | tension (b)\n"
        "part: a | Force on block (b)\nanswer: F | 3 | N\npart: b | Tension\nanswer: T | 4 | N"
    )
    assert [ask.meaning for ask in parts.required] == ["force on block (b)", "tension"]
    assert parts.parts[0].title == "Force on block (b)"


def test_a_conclusion_is_written_in_words_on_its_card() -> None:
    """phys30: "yes" in a card drew italic maths letters under an invented symbol."""
    solution = _solution(
        "required: s | whether it slides back\nanswer: s | yes | | static friction cannot hold it"
    )
    assert "$\\text{yes}$ (static friction cannot hold it)" in render_worked(solution, OTHER)
    # Asked by its words: no invented symbol in maths for a conclusion.
    assert "whether it slides back" in render_worked(solution, OTHER)
    assert "$s$ (whether it slides back)" not in render_worked(solution, OTHER)


def test_a_conclusion_is_asked_by_its_words_however_its_symbol_is_braced() -> None:
    """Gemini on #2489: s_1 in Find and s_{1} in the answer are one symbol."""
    solution = _solution(
        "required: s_1 | whether it slides back\n"
        "answer: s_{1} | yes | | static friction cannot hold it"
    )
    assert "$s_1$ (whether it slides back)" not in render_worked(solution, OTHER)
    assert "whether it slides back" in render_worked(solution, OTHER)


def test_a_conclusion_with_no_symbol_asks_by_its_words() -> None:
    """Gemini on #2489: "answer: | yes, …" in the contract's own syntax kept "$s$" in
    Required; the quantity a part also asks keeps its symbol."""
    solution = _solution(
        "required: s | whether all the ice melts\nrequired: Q | heat supplied\n"
        "answer: Q | 5000 | J\nanswer: | yes, all the ice melts | | the heat is enough"
    )
    shown = render_worked(solution, OTHER)
    assert "$s$" not in shown
    assert "whether all the ice melts" in shown
    assert "$Q$ (heat supplied)" in shown


@pytest.mark.parametrize("value", ["mg", "kx", "ma"])
def test_an_answer_in_symbols_stays_maths(value: str) -> None:
    """Claude on #2489: "F | mg | N" was set upright as words and its symbol left
    Required. It is a formula in symbols, drawn as one (a unit after letters is left off,
    as for any answer in symbols: "mg N" reads as a product)."""
    solution = _solution(f"required: F | normal force\nanswer: F | {value} | N")
    shown = render_worked(solution, OTHER)
    assert "\\text{" not in shown
    assert f"$F = {value}$" in shown
    assert "$F$ (normal force)" in shown


@pytest.mark.parametrize(("symbol", "value"), [("x", "ab"), ("A", "lw"), ("x", "a"), ("F", "mg")])
def test_an_answer_in_symbols_with_no_unit_stays_maths(symbol: str, value: str) -> None:
    """Gemini on #2489: a run of letters with no unit is symbols, never a conclusion."""
    solution = _solution(f"required: {symbol} | the result\nanswer: {symbol} | {value} |")
    shown = render_worked(solution, OTHER)
    assert "\\text{" not in shown
    assert f"${symbol} = {value}$" in shown
    assert f"${symbol}$ (the result)" in shown


@pytest.mark.parametrize("value", ["yes", "all the ice melts"])
def test_a_conclusion_is_words_with_or_without_its_symbol(value: str) -> None:
    solution = _solution(f"required: s | whether all the ice melts\nanswer: s | {value} |")
    shown = render_worked(solution, OTHER)
    assert f"\\text{{{value}}}" in shown
    assert "$s$" not in shown


def test_an_unnamed_conclusion_concludes_its_own_part_s_ask() -> None:
    """Gemini on #2489: a yes in part (b) took part (a)'s symbol out of Required."""
    solution = _solution(
        "required: Q_{total} | heat needed to melt all the ice\n"
        "required: s | whether all the ice melts\n"
        "part: a | Heat needed\nanswer: Q | 5000 | J\n"
        "part: b | Does it all melt\nanswer: | yes, all the ice melts | |"
    )
    shown = render_worked(solution, OTHER)
    assert "$Q_{total}$ (heat needed to melt all the ice)" in shown
    assert "$s$" not in shown


def test_a_conclusion_s_tex_specials_are_escaped() -> None:
    """Review of phys30: "yes & no" in ``\\text{}`` broke the group."""
    from app.modules.chat.worked_render import words_tex

    assert words_tex("yes & no") == "\\text{yes \\& no}"
    assert words_tex("yes, since $\\mu_s < \\tan\\theta$") == (
        "\\text{yes, since }\\mu_s < \\tan\\theta"
    )


_LAMP = (
    "given: V | 220 | V | rated voltage\n"
    "given: P | 60 | W | rated power\n"
    "required: meaning | what the numbers mean\n"
    "required: I | current\n"
    "part: a | Meaning of the rated values\n"
    "say: The lamp uses $60\\,\\mathrm{W}$ of power when it runs on $220\\,\\mathrm{V}$.\n"
    "answer: | It takes 60 W when it is run on 220 V | |\n"
    "part: b | Current\n"
    "formula: Electric power | P = VI\n"
    "substitution: I = \\frac{60}{220}\n"
    "answer: I | 0.273 | A\n"
)


def test_a_part_asked_in_words_is_said_in_words_and_carded_as_a_sentence() -> None:
    """G8 t42, 2026-11-18: "What do these numbers mean?" was set as one italic formula under
    Substitution, run off the screen, and the parts after it got no cards."""
    shown = render_worked(_solution(_LAMP), PHYSICS)
    part_a = shown.split("**(a) Meaning of the rated values**")[1].split("---")[0]
    assert "**Substitution**" not in part_a
    assert (
        "\n\nThe lamp uses $60\\,\\mathrm{W}$ of power when it runs on $220\\,\\mathrm{V}$.\n\n"
        in (part_a)
    )
    assert "```answer\nverified: false\nIt takes $60$ W when it is run on $220$ V\n```" in part_a
    assert "**Answer (b)**\n\n$0.273\\,\\mathrm{A}$" in shown
    assert "(a) what the numbers mean" in shown


def test_a_say_line_keeps_its_own_maths_marks() -> None:
    record = read_record("say: $P$ is the power and $V$ the voltage")
    assert isinstance(record, Step) and record.kind == "say"
    assert record.tex == "$P$ is the power and $V$ the voltage"


def test_a_note_that_only_restates_the_value_is_dropped() -> None:
    """G8 t28: "1.03 x 10^5." was left alone under each card, with no unit."""
    solution = _solution(
        "required: P | pressure\nformula: Liquid pressure | P = \\rho g h\n"
        "substitution: P = 1030 \\times 10 \\times 10\n"
        "answer: P | 103000 | Pa | 1.03 \\times 10^{5}\n"
    )
    shown = render_worked(solution, PHYSICS)
    assert "10^{5}" not in shown and "$103000\\,\\mathrm{Pa}$" in shown
    east = _solution("required: v | velocity\nanswer: v | 20 | m/s | east\n")
    assert "(east)" in render_worked(east, PHYSICS)


def test_a_ph_keeps_its_decimals() -> None:
    """Review: a pH's decimals are its concentration's figures, never the card rule's."""
    shown = render_worked(_solution("required: pH | pH\nanswer: pH | 2.874 |\n"), OTHER)
    assert "2.874" in shown
