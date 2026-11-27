"""A reply never offers to set a reminder: chat only reads to-dos (owner, 2026-11-27)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.modules.todos.reply_offers import (
    CARD_LANGS,
    asked_about_a_change,
    follows_todo_reply,
    without_reminder_offers,
)

# Live 2026-10-25: the offer a yes was then taken for.
LIVE_OFFER = (
    "I can definitely help you practise. Would you like me to set up that **Practice list "
    "comprehensions** reminder for tomorrow (Monday) at 7:00 PM?"
)


@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        (LIVE_OFFER, "I can definitely help you practise."),
        ("Here's the plan. Want me to set a reminder for tomorrow at 7?", "Here's the plan."),
        ("Shall I remind you at 7 or 8?", ""),
        (
            "Great job! Want a quiz on this, or should I set a reminder?",
            "Great job! Want a quiz on this?",
        ),
        (
            "Done.\n\nWould you like me to add milk to your shopping list? Let me know.",
            "Done.\n\nLet me know.",
        ),
        ("Should I add it to your to-do list?", ""),
        ("Do you want a reminder for the test?", ""),
    ],
)
def test_an_offer_to_set_a_reminder_goes(reply: str, kept: str) -> None:
    assert without_reminder_offers(reply) == kept


@pytest.mark.parametrize(
    "reply",
    [
        "Do you want a reminder of the key steps?",
        "Should I add error handling to the reminder service?",
        "Want me to build a to-do list app with you?",
        "Want a practice problem?",
        "Should I explain how reminders work on iPhone?",
        "Shall I remind you how the formula works?",
    ],
)
def test_a_question_about_something_else_stays(reply: str) -> None:
    assert without_reminder_offers(reply) == reply


def test_an_offer_under_code_offers_code() -> None:
    reply = 'Here:\n\n```tsx\n<input name="due" />\n```\n\nShould I add a reminder field to it?'
    assert without_reminder_offers(reply) == reply


@pytest.mark.parametrize(
    "card",
    [
        "```steps\n1. **Plan** — pick a topic\n2. **Start** — 20 minutes\n```",
        '```quiz\n{"question": "Mass number?", "options": ["17", "35"], "answer": 1}\n```',
        "```math\nx = 2\n```",
    ],
)
def test_an_offer_under_the_apps_card_still_goes(card: str) -> None:
    reply = f"Here's the plan:\n\n{card}\n\nWant me to remind you to start this tomorrow?"
    assert without_reminder_offers(reply) == f"Here's the plan:\n\n{card}"


_REGISTRY = Path(__file__).resolve().parents[5] / "mobile" / "lib" / "fence" / "registry.ts"


def test_every_card_the_phone_draws_is_no_code() -> None:
    found = {
        lang.strip().strip("\"'")
        for match in re.finditer(r"langs:\s*\[([^\]]*)\]", _REGISTRY.read_text(encoding="utf-8"))
        for lang in match.group(1).split(",")
        if lang.strip()
    }
    assert {"quiz", "steps", "math"} <= found
    assert found <= CARD_LANGS, sorted(found - CARD_LANGS)


@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        ("Deleted. If you start at home, I can set a reminder for that instead.", "Deleted."),
        # The reminder's own times are no other offer.
        ("When should I remind you — tomorrow morning, or on your way home at 6 PM?", ""),
        ("Want me to delete your **gym** reminder so it stops nagging you?", ""),
    ],
)
def test_an_offer_said_any_way_goes(reply: str, kept: str) -> None:
    assert without_reminder_offers(reply) == kept


@pytest.mark.parametrize(
    "reply",
    [
        "I can't set reminders here.",
        "We could set a reminder email for the team.",
        "Should I add a reminder banner to the hero?",
    ],
)
def test_a_denial_or_another_thing_stays(reply: str) -> None:
    assert without_reminder_offers(reply) == reply


@pytest.mark.parametrize(
    ("prior", "follows", "asked"),
    [
        ("You can add or change it in **To-do**.\n\n```todo_link\n```", True, False),
        ("Set: gym — Thursday, Oct 15, 6:00 PM.", True, False),
        ("Pack layers.\n\nWant me to set a reminder to check in online?", True, True),
        ("Sure. When should I remind you?", True, True),
        ("Here's your routine.\n\nWhat time should I set it for?", False, False),
        ("Friday's meeting has been moved to 3:00 PM.", False, False),
        (None, False, False),
    ],
)
def test_a_reply_about_a_change(prior: str | None, follows: bool, asked: bool) -> None:
    assert follows_todo_reply(prior) is follows
    assert asked_about_a_change(prior) is asked
