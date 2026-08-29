from app.services.md_fence_scan import close_unclosed_fences, strip_closed_fences


def test_strip_closed_fences_leaves_following_opener() -> None:
    text = "Intro\n```answer\n42\n```\n```python\nprint(1)\n```\n"
    assert "42" not in strip_closed_fences(text, "answer")
    assert "```python" in strip_closed_fences(text, "answer")


def test_close_unclosed_fences_adds_closer() -> None:
    open_mermaid = "```mermaid\ngraph TD\n  A-->B"
    closed = close_unclosed_fences(open_mermaid)
    assert closed.rstrip().endswith("```")
    assert close_unclosed_fences("plain prose") == "plain prose"
