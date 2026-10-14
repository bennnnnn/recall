"""Search gates the behavior sweep found too eager or too shy."""

import pytest

from app.modules.web_search import names_its_place
from app.modules.web_search.detection import _live_lookup_cue, needs_web_search_heuristic
from app.modules.web_search.patterns import is_correspondence_request


@pytest.mark.parametrize(
    "text",
    [
        "Finish line results from Sunday's Chicago Marathon?",
        "What time is sunset tomorrow in Cape Town?",
        "How much is an iPhone 17 in Ethiopia?",
        "Can you get me a cheap flight to Nairobi?",
        "Do I need a visa for Kenya with an Ethiopian passport?",
        "What's scheduled at the Hollywood Bowl this weekend?",
    ],
)
def test_live_facts_ask_the_search_classifier(text: str) -> None:
    assert _live_lookup_cue(text)


@pytest.mark.parametrize(
    "text",
    ["how much is 3 + 4", "what is a derivative", "priceless memories", "her visage"],
)
def test_schoolbook_questions_have_no_live_cue(text: str) -> None:
    assert not _live_lookup_cue(text)


@pytest.mark.parametrize(
    "text",
    [
        "What is the current in a circuit with 12 V across 4 ohms today?",
        "What date is 100 days from tomorrow?",
        "write a text to cancel my haircut at 2pm today",
    ],
)
def test_not_news(text: str) -> None:
    assert not needs_web_search_heuristic(text)


def test_correspondence_requests() -> None:
    assert is_correspondence_request("write a text to cancel my haircut at 2pm today")
    assert is_correspondence_request("can you help me draft an email to my landlord")
    assert not is_correspondence_request("what's the latest news today")


@pytest.mark.parametrize(
    ("text", "named"),
    [
        ("Best Ethiopian restaurant in DC that's open right now?", True),
        ("Get directions to Bole airport from Piassa", True),
        ("What's open near me in Bole?", True),
        ("best pizza in town?", False),
        ("Directions to the airport", False),
        ("coffee near me", False),
        ("In my area, best tacos?", False),
    ],
)
def test_names_its_place(text: str, named: bool) -> None:
    assert names_its_place(text) is named
