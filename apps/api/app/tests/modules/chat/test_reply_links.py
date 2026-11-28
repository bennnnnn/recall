"""Every link a reply shows opens what the server can stand behind (T5.11), and a name the
reply marks to look up opens its own site, Maps or a search (the owner, 2026-11-27)."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit
from app.modules.chat.finalize_passes import FinalizeState
from app.modules.chat.name_links import is_a_name, name_target, own_site
from app.modules.chat.reply_links import link_reply_names, place_marks_only
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.modules.chat.untrusted_media import neutralize_untrusted_media

FIXTURE = Path(__file__).resolve().parents[6] / "docs" / "fixtures" / "name_links.json"
_FIXTURE = json.loads(FIXTURE.read_text(encoding="utf-8"))
NAME_CASES = _FIXTURE["cases"]
MARKDOWN_CASES = _FIXTURE["markdown"]
UNTOUCHED = _FIXTURE["untouched"]

_HITS = [
    WebSearchHit(title="Reuters", url="https://www.reuters.com/world/lisbon-2026", snippet="s"),
    WebSearchHit(title="BBC", url="https://bbc.com/news/123/", snippet="s"),
]
_RESTAURANT_HITS = [
    WebSearchHit(
        title="The 38 essential SF restaurants", url="https://www.eater.com/sf-38", snippet="s"
    ),
    WebSearchHit(title="Zuni Café", url="https://zunicafe.com/menu", snippet="s"),
    WebSearchHit(title="Nopa", url="https://www.nopasf.com/", snippet="s"),
    WebSearchHit(title="Nopalito", url="https://nopalitosf.com/", snippet="s"),
]
_MAPS = "https://www.google.com/maps/search/?api=1&query="
_SEARCH = "https://www.google.com/search?q="


def _state(
    reply: str, *, hits: list[WebSearchHit] | None = None, message: str = "q"
) -> FinalizeState:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="qwen-3.7-flash",
        prompt_messages=[{"role": "user", "content": message}],
        run_title=False,
        user_message_content=message,
        reserved_tokens=0,
        max_output_tokens=0,
        search_sources=_HITS if hits is None else hits,
    )
    return FinalizeState(
        deps=None,  # type: ignore[arg-type]  # these passes read no dependency
        settings=Settings(),
        ctx=ctx,
        raw=reply,
        text=reply,
        usage={},
        outcome=TurnOutcome(),
        was_cancelled=False,
        should_cancel=None,
    )


def test_a_made_up_page_that_names_nothing_keeps_only_its_words() -> None:
    reply = (
        "According to [Reuters](https://reuters.com/world/lisbon-2026), it rained. "
        "See also [the city's page](https://lisbon-weather-facts.example/2026)."
    )
    out = link_reply_names(_state(reply))
    assert "[Reuters](https://reuters.com/world/lisbon-2026)" in out
    assert "lisbon-weather-facts.example" not in out
    assert "See also the city's page." in out


@pytest.mark.parametrize(
    "link",
    [
        # The same page, written another way.
        "[BBC](http://www.bbc.com/news/123)",
        # The home page of a site a result came from.
        "[Reuters](https://www.reuters.com/)",
        # A map search or directions for a place, and a web search: searches, not claims.
        "[Café](https://www.google.com/maps/search/?api=1&query=Cafe+Lisboa)",
        "[Walking directions](https://www.google.com/maps/dir/?api=1&destination=Belem)",
        "[Atomic Habits](https://www.google.com/search?q=Atomic+Habits)",
        # Not a web page.
        "[mail us](mailto:hi@example.com)",
    ],
)
def test_links_that_are_not_made_up_stay(link: str) -> None:
    reply = f"Details: {link}."
    assert link_reply_names(_state(reply)) == reply


def test_the_users_own_link_stays_but_not_one_in_their_file() -> None:
    message = "summarise https://example.org/report-2026 for me and search for reactions"
    reply = "The [report](https://example.org/report-2026) says rents rose."
    assert link_reply_names(_state(reply, message=message)) == reply
    attached = "summarise this\n[File: notes.txt]\nsee https://evil.example/leak"
    leaked = "The [notes](https://evil.example/leak) say so."
    assert link_reply_names(_state(leaked, message=attached)) == "The notes say so."


def test_code_is_copied_as_written_and_a_fenced_mark_keeps_its_words() -> None:
    reply = (
        "Use `[x](https://made-up.example)` or `[Zuni](check)` in markdown.\n\n"
        '```steps\n1. **Download [Python](check)**\nFrom [Python](check "Online").\n```'
    )
    out = link_reply_names(_state(reply))
    assert out.startswith("Use `[x](https://made-up.example)` or `[Zuni](check)` in markdown.")
    assert "```steps\n1. **Download Python**\nFrom Python.\n```" in out
    assert "](check" not in out.split("```steps")[1]


@pytest.mark.parametrize("case", UNTOUCHED, ids=[case["id"] for case in UNTOUCHED])
def test_maths_code_and_a_target_that_is_no_web_address_are_left_as_written(
    case: dict[str, str],
) -> None:
    """Review of #2618: "$\\mathcal{L}[t^2](s)$" saved as "$\\mathcal{L}t^2$"."""
    assert link_reply_names(_state(case["text"])) == case["text"]
    assert link_reply_names(_state(case["text"], hits=[])) == case["text"]


def test_a_link_an_earlier_reply_carried_stays() -> None:
    """A follow-up with no search keeps the site an earlier search gave Zuni Café."""
    state = _state("For a date, [Zuni Café](https://zunicafe.com/) is best.", hits=[])
    state.ctx.prompt_messages = [
        {"role": "user", "content": "best restaurants in San Francisco"},
        {"role": "assistant", "content": "1. **[Zuni Café](https://zunicafe.com/)** — classic"},
        {"role": "user", "content": "which of those is best for a date?"},
    ]
    assert link_reply_names(state) == state.text


def test_a_bare_url_as_the_words_becomes_the_site_name() -> None:
    reply = "Source: [https://made-up.example/a](https://made-up.example/a)"
    assert link_reply_names(_state(reply)) == "Source: made-up.example"


def test_an_unmarked_address_no_result_gave_keeps_its_words() -> None:
    """Only a ``check`` mark makes a search: "Read More" or "1" is no name to search, and a
    site the model wrote from memory is no address the server stands behind."""
    reply = (
        "Try [Duolingo](https://www.duolingo-app.example/learn), see [1](https://made-up.example/a), "
        "[Read More](https://x.example/more) or [the docs](https://docs.python.org/3/library/json.html)."
    )
    out = link_reply_names(_state(reply, hits=[]))
    assert out == "Try Duolingo, see 1, Read More or the docs."


def test_an_unmarked_name_opens_its_own_site_from_the_results() -> None:
    reply = "Book at [Zuni Café](https://zuni-cafe-from-memory.example)."
    out = link_reply_names(_state(reply, hits=_RESTAURANT_HITS))
    assert out == "Book at [Zuni Café](https://zunicafe.com/)."


@pytest.mark.parametrize(
    ("link", "kept"),
    [
        # A host with no scheme, from a result: https.
        ("[Nopa](www.nopasf.com)", "[Nopa](https://www.nopasf.com)"),
        # Not from a result: its words, never a dead link.
        ("[Tartine](www.tartine-guess.com)", "Tartine"),
        # No web address at all: as written, never this pass's (the phone draws its words).
        ("[Nopa](nopasf.com)", "[Nopa](nopasf.com)"),
        ("[La Taqueria](#)", "[La Taqueria](#)"),
        ("[click](" + "java" + "script:alert(1))", "[click](" + "java" + "script:alert(1))"),
        ("[call](tel:+14155551234)", "[call](tel:+14155551234)"),
    ],
)
def test_a_www_host_is_https_from_a_result_and_anything_else_is_left(link: str, kept: str) -> None:
    out = link_reply_names(_state(f"See {link}.", hits=_RESTAURANT_HITS))
    assert out == f"See {kept}."


def test_a_link_the_user_typed_earlier_in_the_chat_stays() -> None:
    """Turn 1 "summarise https://example.org/report-2026", turn 2 with no search."""
    state = _state("The [report](https://example.org/report-2026) says rents rose.", hits=[])
    state.ctx.prompt_messages = [
        {"role": "user", "content": "summarise https://example.org/report-2026"},
        {"role": "assistant", "content": "It covers rents."},
        {"role": "user", "content": "what did it say about rents?"},
    ]
    state.ctx.user_message_content = "what did it say about rents?"
    assert link_reply_names(state) == state.text


def test_the_closed_strip_places_marks_and_drops_the_rest() -> None:
    text = '[Zuni Café](check "San Francisco") and [Read More](https://x.example)'
    expected = f"[Zuni Café]({_MAPS}Zuni%20Caf%C3%A9%2C%20San%20Francisco) and Read More"
    assert place_marks_only(text) == expected


def test_a_model_image_turned_into_a_link_stays_a_link() -> None:
    """untrusted_media runs first and makes the image a tap-to-open link; it is not a source."""
    state = _state(
        "Here it is: ![a tram](https://img.example/tram.jpg) and [fake](https://x.example/p)"
    )
    state.text = neutralize_untrusted_media(state)
    out = link_reply_names(state)
    assert "[a tram](https://img.example/tram.jpg)" in out
    assert "x.example" not in out and "and fake" in out


def test_marked_names_open_their_own_site_or_maps() -> None:
    reply = (
        "## Best Restaurants in San Francisco\n"
        '1. **[Zuni Café](check "San Francisco")** — Californian, $$$\n'
        '2. **[Nopa](check "San Francisco")** — late dinners, $$\n'
        '3. **[La Taqueria](check "San Francisco")** — tacos, $\n'
        "4. **[Atomic Habits](check)** — a book\n"
        "5. [State Bird Provisions](check:San Francisco) — dim sum carts"
    )
    out = link_reply_names(_state(reply, hits=_RESTAURANT_HITS))
    assert "[Zuni Café](https://zunicafe.com/)" in out
    assert "[Nopa](https://www.nopasf.com/)" in out
    assert f"[La Taqueria]({_MAPS}La%20Taqueria%2C%20San%20Francisco)" in out
    assert f"[Atomic Habits]({_SEARCH}Atomic%20Habits)" in out
    assert f"[State Bird Provisions]({_MAPS}State%20Bird%20Provisions%2C%20San%20Francisco)" in out
    assert "check" not in out


@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        # A heading names what follows; it is no item to tap.
        ("## [Zuni Café](check)\nGreat food.", "## Zuni Café\nGreat food."),
        # A kind of thing, not a name.
        ("Find [a taqueria](check) nearby.", "Find a taqueria nearby."),
        ("Look for [budget phones](check).", "Look for budget phones."),
    ],
)
def test_what_never_gets_a_link_keeps_its_words(reply: str, kept: str) -> None:
    assert link_reply_names(_state(reply, hits=[])) == kept


@pytest.mark.parametrize(
    ("words", "name"),
    [
        ("Zuni Café", True),
        ("**Burma Superstar**", True),
        ("iPhone 16", True),
        ("CS50", True),
        ("ቶሞካ ቡና", True),
        ("a taqueria", False),
        ("1", False),
        ("the city's page", False),
        ("—", False),
        ("Read the full guide to every one of the city's best places here", False),
    ],
)
def test_is_a_name(words: str, name: bool) -> None:
    assert is_a_name(words) is name


def test_own_site_is_a_host_that_names_it() -> None:
    assert own_site("Zuni Café", _RESTAURANT_HITS) == "https://zunicafe.com/"
    # "nopalitosf" is another restaurant's, not Nopa's with a city after it.
    assert own_site("Nopa", _RESTAURANT_HITS[3:]) is None
    # A list article that mentions it is not its site.
    assert own_site("La Taqueria", _RESTAURANT_HITS) is None
    assert own_site(
        "The House of Prime Rib", [WebSearchHit("H", "https://houseofprimerib.net/", "")]
    ) == ("https://houseofprimerib.net/")
    assert own_site("CS50", [WebSearchHit("CS50", "https://cs50.harvard.edu/x/", "")]) == (
        "https://cs50.harvard.edu/"
    )


@pytest.mark.parametrize("case", NAME_CASES, ids=[case["id"] for case in NAME_CASES])
def test_name_target_matches_the_phone(case: dict[str, str]) -> None:
    assert name_target(case["name"], case["city"], []) == case["url"]


def test_a_name_is_linked_the_first_time_only() -> None:
    reply = (
        "1. **[Python Crash Course](check)** — projects.\n"
        "2. **[Automate the Boring Stuff](check)** — scripts.\n\n"
        "Start with **[Python Crash Course](check)**."
    )
    out = link_reply_names(_state(reply, hits=[]))
    assert out.count("Python%20Crash%20Course") == 1
    assert out.endswith("Start with **Python Crash Course**.")


@pytest.mark.parametrize("case", MARKDOWN_CASES, ids=[case["id"] for case in MARKDOWN_CASES])
def test_a_marked_link_as_written_opens_what_the_phone_opens(case: dict[str, str]) -> None:
    assert f"]({case['url']})" in place_marks_only(case["markdown"])


def test_a_city_with_its_own_brackets_keeps_the_saved_link_whole() -> None:
    reply = """Try [Joe's Pizza](check "New York (Greenwich Village)")."""
    out = link_reply_names(_state(reply, hits=[]))
    target = out[out.index("](") + 2 : -2]
    assert target.count("(") == target.count(")") == 0
    assert out.endswith("%28Greenwich%20Village%29).")
