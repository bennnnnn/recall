from app.services.md_fence_scan import (
    close_unclosed_fences,
    replace_first_closed_fence_body,
    strip_closed_fences,
)


def test_strip_closed_fences_leaves_following_opener() -> None:
    text = "Intro\n```answer\n42\n```\n```python\nprint(1)\n```\n"
    assert "42" not in strip_closed_fences(text, "answer")
    assert "```python" in strip_closed_fences(text, "answer")


def test_close_unclosed_fences_adds_closer() -> None:
    open_mermaid = "```mermaid\ngraph TD\n  A-->B"
    closed = close_unclosed_fences(open_mermaid)
    assert closed.rstrip().endswith("```")
    assert close_unclosed_fences("plain prose") == "plain prose"


def test_replace_first_closed_fence_body_keeps_surrounding_prose() -> None:
    text = "Intro\n```email\nTo: a@b.com\nSubject: Hi\n\nHello\n```\nOutro\n"
    next_text = replace_first_closed_fence_body(
        text, "email", "To: b@c.com\nSubject: Bye\n\nShorter"
    )
    assert next_text is not None
    assert next_text.startswith("Intro\n```email\n")
    assert "To: b@c.com" in next_text
    assert "Shorter" in next_text
    assert "Hello" not in next_text
    assert next_text.endswith("```\nOutro\n")


def test_replace_first_closed_fence_body_returns_none_without_fence() -> None:
    assert replace_first_closed_fence_body("plain", "email", "Hi") is None
