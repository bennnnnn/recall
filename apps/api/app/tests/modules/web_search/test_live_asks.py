"""Job openings and prices search without waiting on the classifier (T5.2, T5.8).

Each rule names what is looked up, so the look-alikes ("I got the job", "cron job",
"the price of freedom") stay ordinary chat.
"""

from __future__ import annotations

import pytest

from app.modules.web_search.detection import needs_web_search, web_search_fast_yes
from app.modules.web_search.live_asks import (
    asks_for_a_price,
    asks_for_entry_rules,
    asks_for_job_listings,
)


@pytest.mark.parametrize(
    "text",
    [
        "find remote backend engineering jobs",
        "find software jobs posted today",
        "remote python developer openings",
        "any data analyst vacancies in Nairobi?",
        "who is hiring react developers right now",
        "job openings at Google",
        "find me a job as a nurse in Nairobi",
        "show me software engineering internships in Berlin",
        "what jobs are available for nurses in Kenya",
        "I want to find remote backend engineering jobs",
        "entry-level marketing roles in London",
    ],
)
def test_job_listings_search_at_once(text: str) -> None:
    assert asks_for_job_listings(text)
    assert web_search_fast_yes(text)
    assert needs_web_search(text)


@pytest.mark.parametrize(
    "text",
    [
        "I got the job",
        "set up a cron job that runs every night",
        "job interview tips",
        "write a cover letter for a backend job",
        "how do I find a job after college",
        "you're doing a great job today",
        "what jobs can I get with a biology degree",
        "best jobs for introverts",
        "tell me about Steve Jobs",
        "the jobs to be done framework",
        "my celery jobs keep failing",
        "chess openings for beginners",
        "best yoga positions for back pain",
        "I'm looking for a new job",
        "what is a job description",
        "kubernetes jobs vs cronjobs",
        "I have two jobs and no time",
        "how do I list background jobs in sidekiq",
    ],
)
def test_job_lookalikes_are_not_listings(text: str) -> None:
    assert not asks_for_job_listings(text)


@pytest.mark.parametrize(
    "text",
    [
        "how much does the iPhone 17 Pro cost?",
        "how much does the iphone 17 pro cost",
        "bitcoin price today",
        "what is the current price of bitcoin?",
        "USD to ETB exchange rate",
        "usd to etb",
        "how many birr is a dollar",
        "price of gold today",
        "Tesla stock price",
        "how much is a PS5 now",
        "what's the price of a MacBook Air M4",
    ],
)
def test_prices_search_at_once(text: str) -> None:
    assert asks_for_a_price(text)
    assert web_search_fast_yes(text)


@pytest.mark.parametrize(
    "text",
    [
        "what's the price of freedom",
        "how should I price my online course",
        "what is price elasticity of demand",
        "If apples cost $2 each, how much do 5 apples cost?",
        "the price is right",
        "how much does it cost to build a house",
        "write a poem about the price of fame",
        "what's a good pricing strategy for a startup",
        "how much do you love me",
        "price discrimination examples",
        "how much is 2x + 3 when x = 4",
    ],
)
def test_price_lookalikes_are_not_lookups(text: str) -> None:
    assert not asks_for_a_price(text)


@pytest.mark.parametrize(
    "text",
    [
        "UK visa rules for Ethiopian citizens",
        "do I need a visa for Japan?",
        "visa requirements for Kenya",
        "is there visa on arrival in Rwanda",
    ],
)
def test_visa_rules_search_at_once(text: str) -> None:
    assert asks_for_entry_rules(text)
    assert web_search_fast_yes(text)


@pytest.mark.parametrize(
    "text",
    [
        "what is a visa",
        "write a cover letter for my visa application",
        "my Visa card was declined",
        "how do I pay with Visa on Amazon",
    ],
)
def test_visa_lookalikes_are_not_rules(text: str) -> None:
    assert not asks_for_entry_rules(text)
