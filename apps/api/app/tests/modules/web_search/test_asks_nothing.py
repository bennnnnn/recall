import pytest

from app.modules.web_search.asks_nothing import asks_nothing_to_look_up


@pytest.mark.parametrize(
    "text",
    [
        "Hello there how is your day going because you are doing a great job today",
        "Thanks, that was really helpful today",
        "I just watched the news and I feel overwhelmed",
        "Prices at the market were crazy high today",
        "Glad it's Friday today",
        "Write a short poem about today",
        "Teach me something new today",
        "What should I cook for dinner tonight with chicken and rice?",
        "What a day today, so much happened",
    ],
)
def test_asks_nothing_to_look_up_statements_and_requests_to_make(text):
    assert asks_nothing_to_look_up(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "latest news about Ethiopia",
        "the score of my team's game today",
        "the price of gold went up again today in London",
        "What's open near me right now?",
        "where should I eat tonight?",
        "Do I need a visa for Kenya with an Ethiopian passport?",
        "We need a hotel in Paris",
        "I want the latest news on the AI Act",
        "Write a summary of today's news",
        "Is it going to rain tonight in London?",
    ],
)
def test_asks_nothing_to_look_up_keeps_lookups(text):
    assert asks_nothing_to_look_up(text) is False
