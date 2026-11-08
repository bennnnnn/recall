"""A search hit's line is the message's words as a reader sees them, never its markdown."""

import json
import os
from pathlib import Path

import pytest

from app.modules.search.snippet import reader_text, snippet
from app.tests.behavior.latex_check import latex_problems

_FIXTURES = Path(__file__).resolve().parents[6] / "docs" / "fixtures"


@pytest.mark.parametrize(
    "markdown, shown",
    [
        ("Physics is taught by **Ms. Okafor**.", "Physics is taught by Ms. Okafor."),
        ("🔐 Your locker code is **31-07-22**.", "🔐 Your locker code is 31-07-22."),
        (
            "Use __bold__, *italic*, _soft_ and ~~old~~ text.",
            "Use bold, italic, soft and old text.",
        ),
        (
            "## Plan\n- **Day 1:** fly\n- [ ] pack\n> keep the receipt",
            "Plan Day 1: fly pack keep the receipt",
        ),
        ("1. Mix\n2. Bake", "1. Mix 2. Bake"),
        (
            "See [the docs](https://example.com) and ![a cat](https://x.y/cat.png).",
            "See the docs and a cat.",
        ),
        ("Run `pip install **x**` first.", "Run pip install **x** first."),
        ("| Item | Cost |\n|---|---:|\n| Rent | $900 |", "Item · Cost Rent · $900"),
        ("Above\n\n---\n\nBelow", "Above Below"),
        ("line one<br>line two", "line one line two"),
        ("Area is \\(\\pi r^2\\) here.", "Area is $\\pi r^2$ here."),
        (
            "A 2*3*4 product, a snake_case_name and List<String>.",
            "A 2*3*4 product, a snake_case_name and List<String>.",
        ),
        ("I saved $50 and $92 this month.", "I saved $50 and $92 this month."),
        ("Escaped \\*star\\* stays.", "Escaped *star* stays."),
    ],
)
def test_reader_text_drops_markdown_marks(markdown, shown):
    assert reader_text(markdown) == shown


def test_reader_text_keeps_code_and_drops_cards():
    markdown = (
        "Here is the loop:\n```python\nfor i in range(3):\n    print(i)\n```\n"
        'And your savings:\n```calculator\n{"label": "Monthly deposit"}\n```\nDone.'
    )
    assert reader_text(markdown) == (
        "Here is the loop: for i in range(3): print(i) And your savings: Done."
    )


@pytest.mark.parametrize(
    "code",
    ["[server]\nport = 8080", "{ a: 1, port: 8080 }", "[port for port in ports]"],
)
def test_snippet_finds_a_match_in_code_that_opens_with_a_bracket(code):
    """Only a JSON body is a card's data; code that opens with a bracket is still read."""
    body = f"Here is the config:\n```text\n{code}\n```\nThat should do it."
    assert "port" in snippet(body, "port")


def test_reader_text_reads_a_long_unpaired_body_quickly():
    hostile = "**" + "a " * 50_000 + "_" * 10_000
    assert reader_text(hostile).startswith("**a a")


def test_snippet_cuts_the_readable_text_around_the_match():
    body = (
        "Here is your schedule for the week ahead. Your physics class is taught by "
        "**Ms. Okafor** in room 12, and chemistry is on Thursday afternoons."
    )
    shown = snippet(body, "okafor")
    assert "**" not in shown
    # The cut lands between words, so no word is shown in part.
    assert shown == (
        "…Your physics class is taught by Ms. Okafor in room 12, and chemistry is on "
        "Thursday afternoons."
    )


def test_snippet_of_a_short_message_is_the_whole_message():
    assert snippet("🔐 Your locker code is **31-07-22**.", "locker") == (
        "🔐 Your locker code is 31-07-22."
    )


def test_snippet_matched_only_in_marks_shows_the_opening_words():
    body = 'Totals below.\n```vega\n{"title": "needle"}\n```\n' + "word " * 60
    shown = snippet(body, "needle")
    assert shown.startswith("Totals below. word word")
    assert shown.endswith("…")
    assert len(shown) <= 121


def test_snippet_cuts_a_long_word_where_it_falls():
    body = "a" * 300 + " needle " + "b" * 300
    shown = snippet(body, "needle")
    assert shown == "…" + "a" * 39 + " needle " + "b" * 79 + "…"


# A worked reply's hit showed its TeX: "…$t$ = time Required $a$…", "$v_0 = 20\\,\\mathrm{m/s}$".
# Each formula is kept whole between ``$`` marks for the phone to show as symbols.
@pytest.mark.parametrize(
    "markdown, shown",
    [
        ("where $t$ = time **Required** $a$", "where $t$ = time Required $a$"),
        (
            "The mean is\n$$\n\\bar{x} = \\frac{1}{n}\n$$\nhere.",
            "The mean is $\\bar{x} = \\frac{1}{n}$ here.",
        ),
        ("Solve:\n\\[ x = \\pm 2 \\]", "Solve: $x = \\pm 2$"),
        ("```math\nE = mc^2\n```", "$E = mc^2$"),
        (
            "**Answer**\n```answer\nverified: true\n3.97\\,\\mathrm{J}\n```",
            "Answer $3.97\\,\\mathrm{J}$",
        ),
        (
            "```answer\nverified: false\nIt moves $4\\,\\mathrm{m}$.\n```",
            "It moves $4\\,\\mathrm{m}$.",
        ),
        ("```answer\nnotation: chemistry\n2H₂ + O₂ → 2H₂O\n```", "2H₂ + O₂ → 2H₂O"),
        ("```tip\nRemember **$F = ma$**.\n```", "Remember $F = ma$."),
        ("Let $a_1 * b_2$ and *this*.", "Let $a_1 * b_2$ and this."),
        ("I saved $50 and **$92** today.", "I saved $50 and $92 today."),
        ("Run `echo $HOME $PATH` first.", "Run echo \\$HOME \\$PATH first."),
        ("```bash\necho $HOME $PATH\n```", "echo \\$HOME \\$PATH"),
        # An answer in words is words: "$12 cm$" showed like a price.
        ("```answer\nverified: false\n12 cm\n```", "12 cm"),
        ("```answer\nverified: false\n5 cups of flour\n```", "5 cups of flour"),
        # Code is set aside before formulas are found: `\(x\)` in code stays code.
        (
            'Use `\\(x\\)` and `re.match(r"\\(\\d+\\)")`, then \\(y\\).',
            'Use \\(x\\) and re.match(r"\\(\\d+\\)"), then $y$.',
        ),
        ("$a$$b$ side by side", "$a$$b$ side by side"),
        # A formula too long to show is "…", so a hit stays short.
        ("x $" + "a+" * 1100 + "b$ y", "x … y"),
        ("x\n$$\n" + "a+" * 1100 + "b\n$$\ny", "x … y"),
    ],
)
def test_reader_text_keeps_each_formula_whole(markdown, shown):
    assert reader_text(markdown) == shown


def _replies(name: str) -> list[str]:
    data = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    return [entry["reply"] for entry in data["replies"].values()]


@pytest.mark.parametrize(
    "reply", _replies("physics_replies.json") + _replies("chemistry_replies.json")
)
def test_snippet_of_a_server_reply_shows_no_tex_outside_a_formula(reply):
    """Wherever the cut falls, a formula is whole or left out: no TeX reaches the words."""
    text = reader_text(reply)
    assert "verified:" not in text
    for word in {word.strip(".,:()") for word in text.split() if word.isalpha() and len(word) > 3}:
        shown = snippet(reply, word)
        assert not [problem for problem in latex_problems(shown) if "outside" in problem], shown


def test_snippet_keeps_the_matched_formula_whole_and_leaves_a_cut_one_out():
    formula = "$v_0 = 20\\,\\mathrm{m/s} + \\frac{a+b}{c}$"
    body = "Lead " + "word " * 10 + formula + " and then the time required " + "tail " * 30
    assert formula in snippet(body, "frac")
    shown = snippet(body, "time")
    assert shown.startswith("…and then the time required")
    # No match: the opening words, ending before a formula the length would cut.
    assert snippet("Lead " + "word " * 20 + formula + " tail" * 30, "zzz") == (
        "Lead " + " ".join(["word"] * 20) + "…"
    )


_SNIPPET_FIXTURE = _FIXTURES / "search_snippets.json"


def test_snippet_fixture_holds_the_lines_the_server_cuts():
    """The server's half of ``docs/fixtures/search_snippets.json``; the phone's
    ``features/search/model/__tests__/snippetFixture.test.ts`` shows the same lines, so the two
    cannot drift. ``UPDATE_SEARCH_SNIPPETS=1`` rewrites the lines after a deliberate change."""
    data = json.loads(_SNIPPET_FIXTURE.read_text(encoding="utf-8"))
    lines = [snippet(case["markdown"], case["query"]) for case in data["cases"]]
    if os.environ.get("UPDATE_SEARCH_SNIPPETS"):
        for case, line in zip(data["cases"], lines, strict=True):
            case["snippet"] = line
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        _SNIPPET_FIXTURE.write_text(text, encoding="utf-8")
    assert lines == [case["snippet"] for case in data["cases"]]


def test_snippet_matches_what_shows_not_a_command_name():
    """ "time" inside ``\\times`` drew nothing highlighted; the hit is the visible "times"."""
    body = "Use $a \\times b$ " + "x " * 40 + "then the times table."
    assert snippet(body, "time").endswith("then the times table.")


@pytest.mark.parametrize(
    "hostile",
    ["\\[" * 50_000, "\\( a " * 50_000, "$$ a " * 50_000, "$x$ " * 50_000, "$" + "ab " * 100_000],
)
def test_reader_text_finds_formulas_in_linear_time(hostile):
    assert isinstance(snippet(hostile, "a"), str)
