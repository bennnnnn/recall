"""Tests for shared text normalization helpers."""

from app.services.text_normalize import cap_text_head_tail, collapse_ws


def test_collapse_ws():
    assert collapse_ws("  a \n b\t c  ") == "a b c"


def test_cap_text_head_tail_short_passthrough():
    assert cap_text_head_tail("hello", 4000) == "hello"


def test_cap_text_head_tail_keeps_ends():
    text = "A" * 1000 + "MIDDLE" + "Z" * 1000
    out = cap_text_head_tail(text, max_chars=100)
    assert len(out) == 100
    assert out.startswith("A")
    assert out.endswith("Z")
    assert "…" in out
    assert "MIDDLE" not in out
