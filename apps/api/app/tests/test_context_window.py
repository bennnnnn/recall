"""Tests for token estimation + token-budget window selection."""

from app.services.context_window import estimate_tokens, select_recent_window


class _M:
    def __init__(self, content: str):
        self.content = content


def test_estimate_tokens():
    assert estimate_tokens("") == 1
    assert estimate_tokens("a" * 400) == 100


def test_select_keeps_all_when_under_budget():
    msgs = [_M("hi"), _M("there"), _M("friend")]
    assert select_recent_window(msgs, budget=1000, max_count=40) == 3


def test_select_respects_max_count():
    msgs = [_M("x") for _ in range(50)]
    assert select_recent_window(msgs, budget=10_000, max_count=40) == 40


def test_select_trims_to_budget():
    # each message ~25 tokens (100 chars / 4); budget 60 keeps 2 (3rd would exceed)
    msgs = [_M("a" * 100) for _ in range(10)]
    assert select_recent_window(msgs, budget=60, max_count=40, min_count=2) == 2


def test_select_keeps_min_even_when_over_budget():
    # min_count guarantees the latest exchange survives even if huge
    msgs = [_M("a" * 1000), _M("a" * 1000), _M("a" * 1000)]
    assert select_recent_window(msgs, budget=50, max_count=40, min_count=2) == 2
