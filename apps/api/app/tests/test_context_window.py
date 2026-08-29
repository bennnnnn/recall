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


def test_compute_history_split():
    msgs = [_M("a" * 400) for _ in range(40)]
    split = compute_history_split(60, msgs, budget=6000, max_count=40)
    assert split.keep_count == 40
    assert split.summarized_count == 20
    assert split.token_pressure is False


def test_should_run_compression_batch():
    split = compute_history_split(60, [_M("x")] * 40, budget=6000, max_count=40)
    # summarized_count = 20; pending = 20 - 0 = 20 >= batch(10) → run
    assert should_run_compression(split, already_summarized=0, batch=10) is True
    # pending = 20 - 18 = 2 < urgent_min_pending(3) → wait (small gap amortizes)
    assert should_run_compression(split, already_summarized=18, batch=10) is False


def test_should_run_compression_urgent_without_token_pressure():
    """H5: a gap >= urgent_min_pending must compress even without token
    pressure — otherwise the middle-history hole drops messages that are
    neither in the summary nor in the recent window."""
    msgs = [_M("x")] * 40
    split = compute_history_split(60, msgs, budget=6000, max_count=40)
    assert split.token_pressure is False
    assert split.summarized_count > 0
    assert should_run_compression(split, already_summarized=0, batch=10, urgent_min_pending=3)


def test_should_run_compression_urgent_under_token_pressure():
    msgs = [_M("a" * 400) for _ in range(40)]
    split = compute_history_split(60, msgs, budget=250, max_count=40)
    assert split.token_pressure is True
    assert split.summarized_count > 0
    assert should_run_compression(split, already_summarized=0, batch=10, urgent_min_pending=3)


def test_should_run_compression_small_gap_waits():
    """A 1-2 message gap is too small to justify an LLM summarization call;
    wait for it to grow to urgent_min_pending."""
    split = compute_history_split(60, [_M("x")] * 40, budget=6000, max_count=40)
    # summarized_count = 60 - 40 = 20; already = 18 → pending = 2
    assert (
        should_run_compression(split, already_summarized=18, batch=10, urgent_min_pending=3)
        is False
    )


def test_trim_and_cap_summary():
    long = "word " * 500
    trimmed = trim_message_for_summary(long, max_chars=100)
    assert "[truncated]" in trimmed
    capped = cap_summary("x" * 7000, max_chars=100)
    assert capped.endswith("...")
