"""Tests for token estimation + token-budget window selection."""

from app.services.context_window import (
    cap_summary,
    compute_history_split,
    estimate_tokens,
    select_recent_window,
    should_run_compression,
    trim_message_for_summary,
)


class _M:
    def __init__(self, content: str):
        self.content = content


def test_estimate_tokens():
    assert estimate_tokens("") == 1
    assert estimate_tokens("a" * 400) == 111


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


def test_compute_history_split():
    msgs = [_M("a" * 400) for _ in range(40)]
    split = compute_history_split(60, msgs, budget=6000, max_count=40)
    assert split.keep_count == 40
    assert split.summarized_count == 20
    assert split.token_pressure is False


def test_should_run_compression_batch():
    split = compute_history_split(60, [_M("x")] * 40, budget=6000, max_count=40)
    assert should_run_compression(split, already_summarized=0, batch=10) is True
    assert should_run_compression(split, already_summarized=15, batch=10) is False


def test_should_run_compression_urgent_under_token_pressure():
    msgs = [_M("a" * 400) for _ in range(40)]
    split = compute_history_split(60, msgs, budget=250, max_count=40)
    assert split.token_pressure is True
    assert split.summarized_count > 0
    assert should_run_compression(split, already_summarized=0, batch=10, urgent_min_pending=3)


def test_trim_and_cap_summary():
    long = "word " * 500
    trimmed = trim_message_for_summary(long, max_chars=100)
    assert "[truncated]" in trimmed
    capped = cap_summary("x" * 7000, max_chars=100)
    assert capped.endswith("...")
