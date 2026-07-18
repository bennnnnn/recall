"""Tests for untrusted-content framing helpers."""

from app.services.prompt_safety import wrap_persisted_attachment_excerpts, wrap_untrusted


def test_wrap_untrusted_empty_passthrough():
    assert wrap_untrusted("x", "") == ""
    assert wrap_untrusted("x", "   ") == "   "


def test_wrap_persisted_attachment_excerpts_leaves_plain_text():
    assert wrap_persisted_attachment_excerpts("just a question") == "just a question"


def test_wrap_persisted_attachment_excerpts_wraps_file_tail():
    content = "Please summarize\n\n[File: /attachments/abc/file]\nhello world"
    out = wrap_persisted_attachment_excerpts(content)
    assert out.startswith("Please summarize\n\n[BEGIN UNTRUSTED CONTENT — user attachments]")
    assert "hello world" in out
    assert "[END UNTRUSTED CONTENT — user attachments]" in out
