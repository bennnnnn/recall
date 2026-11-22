"""Tests for token estimation + token-budget window selection."""

import pytest

from app.core.config import Settings
from app.modules.chat.context_window import (
    FoldRule,
    cap_summary,
    estimate_tokens,
    fits_whole,
    messages_within_token_budget,
    select_recent_window,
    total_tokens,
    trim_message_for_summary,
    unsummarized_gap_bounds,
)


class _M:
    def __init__(self, content: str):
        self.content = content


def test_estimate_tokens():
    assert estimate_tokens("") == 1
    assert estimate_tokens("a" * 400) == 111


def test_estimate_tokens_non_latin_is_one_per_char() -> None:
    amharic = "ፕሮጀክቶችፕሮጀክቶችፕሮጀክቶች"
    assert estimate_tokens(amharic) == len(amharic)
    cyrillic = "проекты" * 8
    assert estimate_tokens(cyrillic) == len(cyrillic)


def test_estimate_tokens_vision_content_list():
    """Finalize fallback must not crash when vision turns use list content."""
    parts = [
        {"type": "text", "text": "what is in this image?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
    ]
    assert estimate_tokens(parts) >= 85
    assert estimate_tokens([{"type": "image_url", "image_url": {"url": "x"}}]) == 85
    assert estimate_tokens([]) == 1


def test_estimate_tokens_code_heavier():
    plain = "a" * 400
    code = "```python\n" + ("x = 1\n" * 40) + "```"
    assert estimate_tokens(code) > estimate_tokens(plain)


def test_select_keeps_all_when_under_budget():
    msgs = [_M("hi"), _M("there"), _M("friend")]
    assert select_recent_window(msgs, budget=1000, max_count=40) == 3


def test_select_respects_max_count():
    msgs = [_M("x") for _ in range(50)]
    assert select_recent_window(msgs, budget=10_000, max_count=40) == 40


def test_select_trims_to_budget():
    msgs = [_M("a" * 400) for _ in range(10)]
    assert select_recent_window(msgs, budget=250, max_count=40, min_count=2) == 2


def test_select_keeps_min_even_when_over_budget():
    msgs = [_M("a" * 1000), _M("a" * 1000), _M("a" * 1000)]
    assert select_recent_window(msgs, budget=50, max_count=40, min_count=2) == 2


_RULE = FoldRule(trigger_tokens=1000, trigger_count=10, target_tokens=400, target_count=4)


def test_fits_whole_holds_every_message_to_the_budget_and_the_count():
    rows = [_M("a" * 400) for _ in range(4)]  # 111 tokens each
    assert fits_whole(rows, budget=444, max_count=4)
    assert not fits_whole(rows, budget=443, max_count=4)
    assert not fits_whole(rows, budget=10_000, max_count=3)
    assert not fits_whole([], budget=10_000, max_count=3)
    assert total_tokens(rows) == 444


def test_fold_rule_folds_nothing_under_the_trigger():
    """Between folds the history's first message stays put: that is the cache's prefix."""
    assert _RULE.to_fold([_M("x")] * 10) == 0
    assert _RULE.to_fold([_M("a" * 400)] * 9) == 0  # 999 tokens


def test_fold_rule_folds_back_to_the_target_past_the_message_trigger():
    # 11 short rows pass the count: the newest 4 (the target count) stay.
    assert _RULE.to_fold([_M("x")] * 11) == 7


def test_fold_rule_folds_back_to_the_target_past_the_token_trigger():
    # 10 rows of 111 tokens pass 1000 tokens: 3 of them fit the 400-token target.
    assert _RULE.to_fold([_M("a" * 400)] * 10) == 7


def test_fold_rule_folds_every_unseen_older_message():
    """A backlog the job did not load is folded whatever its size."""
    assert _RULE.to_fold([_M("x")] * 4, unseen=20) == 20


def test_fold_rule_keeps_the_last_exchange_even_when_it_alone_is_over():
    huge = [_M("a" * 4000), _M("a" * 4000), _M("a" * 4000)]
    assert _RULE.to_fold(huge) == 1


def test_shipped_fold_rule_leaves_room_for_the_turns_a_fold_takes():
    """The trigger sits under the prompt's caps, so a chat whose fold is still running is
    carried whole for a few turns more instead of sliding."""
    settings = Settings()
    rule = FoldRule.of(settings)
    assert rule.target_tokens < rule.trigger_tokens < settings.context_token_budget
    assert rule.target_count < rule.trigger_count < settings.history_max_messages
    assert settings.history_max_messages >= settings.recent_message_window


def test_unsummarized_gap_bounds_takes_the_hole_before_the_window():
    # 100 messages, summary covers 70, window holds the last 20 → indexes 70..80.
    assert unsummarized_gap_bounds(total=100, summarized=70, loaded=20) == (70, 10)


def test_unsummarized_gap_bounds_caps_a_long_hole_at_the_newest_messages():
    assert unsummarized_gap_bounds(total=100, summarized=0, loaded=20, max_messages=10) == (70, 10)


def test_gap_messages_stop_when_the_token_budget_is_spent():
    short = _M("hi")
    long = _M("a" * 400)
    fitted = messages_within_token_budget([long, short], budget=20, max_messages=10)
    assert fitted == [short]
    assert messages_within_token_budget([long], budget=0, max_messages=10) == []


def test_unsummarized_gap_bounds_empty_when_summary_reaches_the_window():
    assert unsummarized_gap_bounds(total=100, summarized=80, loaded=20) is None
    assert unsummarized_gap_bounds(total=15, summarized=0, loaded=15) is None


def test_trim_and_cap_summary():
    long = "word " * 500
    trimmed = trim_message_for_summary(long, max_chars=100)
    assert "[truncated]" in trimmed
    assert len(trimmed) <= 100
    capped = cap_summary("x" * 7000, max_chars=100)
    assert capped.endswith("...")


_CV = "Here is my CV:\n" + "Led backend projects in Go; shipped payment systems. " * 30


@pytest.mark.parametrize(
    ("message", "kept"),
    [
        # The ask after a paste is what the summary must hold.
        (f"{_CV}\nI'm applying to Stripe for the senior role, deadline Friday.", "Stripe"),
        # So is the instruction before one.
        (f"Rewrite this for a Stripe application, keep it to one page.\n{_CV}", "Stripe"),
    ],
)
def test_a_long_message_keeps_its_start_and_end_for_the_summary(message, kept):
    trimmed = trim_message_for_summary(message)
    assert len(trimmed) <= 1200 < len(message)
    assert kept in trimmed
    assert "[truncated]" in trimmed


# ── estimate_tokens — O(1) ────────────────────────────────────────────────────


def test_estimate_tokens_empty():
    from app.modules.chat.context_window import estimate_tokens

    assert estimate_tokens("") == 1


def test_estimate_tokens_short():
    from app.modules.chat.context_window import estimate_tokens

    # "hello" → len=5 // 4 = 1, max(1,1)=1
    assert estimate_tokens("hello") == 1


def test_estimate_tokens_long():
    from app.modules.chat.context_window import estimate_tokens

    text = "a" * 400
    assert estimate_tokens(text) == 111
