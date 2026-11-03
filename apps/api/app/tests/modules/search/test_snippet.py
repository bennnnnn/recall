"""A search hit's line is the message's words as a reader sees them, never its markdown."""

import pytest

from app.modules.search.snippet import reader_text, snippet


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
        ("Area is \\(\\pi r^2\\) here.", "Area is \\pi r^2 here."),
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
