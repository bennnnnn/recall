"""Which messages read the saved to-dos back, and which replies are only a clock."""

import pytest

from app.modules.todos.read_asks import asks_to_read_reminders


@pytest.mark.parametrize(
    ("user_text", "reads"),
    [
        ("What's scheduled at the Hollywood Bowl this weekend?", False),
        ("what's scheduled in Paris", False),
        ("whats scheduled for tomorrow", True),
        ("what is scheduled at 3pm", True),
        ("what is scheduled in the morning", True),
        ("what reminders do I have", True),
        # Live 2026-10-25: the model answered both from the chat.
        ("ok last thing, what's on my to do list right now?", True),
        ("hmm are you sure? check my to-do list again", True),
        ("what's on my to-do list?", True),
        ("whats on my todo list", True),
        ("show me my to-dos", True),
        ("wait what's on my to-do list", True),
        ("list my to do list please", True),
        ("what's on my schedule tomorrow", True),
        ("what's on my list and what's 2 + 2?", False),
        ("what are my reminders and can you add milk", False),
        ("check my to-do list and mark gym done", False),
        ("add milk to my to-do list", False),
        ("things to do in lisbon?", False),
        ("what should I add to my to-do list before moving house?", False),
        ("what's on my list for the party? i need ideas", False),
        ("what is the best to-do list app?", False),
        ("Make a to-do plan for my day today", False),
    ],
)
def test_asks_to_read_reminders(user_text, reads):
    assert asks_to_read_reminders(user_text) is reads


@pytest.mark.parametrize(
    ("text", "clock"),
    [
        ("6", (18, 0)),
        # A bare hour reads the same with minutes: the evening, like "6".
        ("6:30", (18, 30)),
        ("at 6:30.", (18, 30)),
        ("11", (23, 0)),
        ("12", (12, 0)),
        ("12:45", (12, 45)),
        ("18", (18, 0)),
        ("23:59", (23, 59)),
        ("6pm", (18, 0)),
        ("6 PM", (18, 0)),
        ("at 7:30 a.m.", (7, 30)),
        ("12am", (0, 0)),
        ("12pm!", (12, 0)),
        # Not a clock. "0" is not noon: midnight is said as midnight or 12am.
        ("0", None),
        ("0:30", None),
        ("00", None),
        ("24", None),
        ("6:75", None),
        ("6:3", None),
        ("1 8", None),
        ("13pm", None),
        ("0am", None),
        ("6pm tomorrow", None),
        ("6pm Sam", None),
        ("call mom", None),
        ("", None),
    ],
)
def test_a_reply_that_is_only_a_clock(text, clock):
    from app.modules.todos.spoken_when import parse_clock_only

    assert parse_clock_only(text) == clock
