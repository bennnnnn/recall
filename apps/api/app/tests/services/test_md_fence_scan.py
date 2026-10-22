import pytest

from app.services.md_fence_scan import (
    close_unclosed_fences,
    iter_fences,
    line_fences,
    map_closed_fences,
    replace_first_closed_fence_body,
    strip_closed_fences,
    strip_gfm_pipe_tables,
    strip_hand_sketch_filler,
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


def test_map_closed_fences_leftover_rewrites_past_cap() -> None:
    text = "```graph\na\n```\n```graph\nb\n```\n"
    out = map_closed_fences(
        text,
        "graph",
        lambda body: f"KEEP:{body.strip()}",
        max_count=1,
        leftover=lambda _body: "DROP",
    )
    assert "KEEP:a" in out
    assert "DROP" in out
    assert "```graph" not in out
    assert "KEEP:b" not in out


def test_map_closed_fences_without_leftover_leaves_tail_past_cap() -> None:
    text = "```graph\na\n```\n```graph\nb\n```\n"
    out = map_closed_fences(
        text,
        "graph",
        lambda body: f"KEEP:{body.strip()}",
        max_count=1,
    )
    assert "KEEP:a" in out
    assert "```graph" in out
    assert "b" in out


def test_strip_gfm_pipe_tables_drops_prose_table_keeps_fenced() -> None:
    text = (
        "Intro\n"
        "### Points to plot\n"
        "| x | y |\n"
        "|---|---|\n"
        "| 1 | 1 |\n"
        "Outro\n"
        "```python\n"
        "| keep | me |\n"
        "|------|----|\n"
        "```\n"
    )
    out = strip_gfm_pipe_tables(text)
    assert "| x |" not in out
    assert "Points to plot" not in out
    assert "Intro" in out
    assert "Outro" in out
    assert "| keep | me |" in out


def test_strip_hand_sketch_filler_drops_ascii_keeps_graph() -> None:
    text = (
        "Parabola at the origin.\n\n"
        "### How to Sketch\n"
        "1. Plot the vertex.\n\n"
        "> ASCII approximation:\n"
        "> ```\n"
        ">   ^ y\n"
        "> ---+--> x\n"
        "> ```\n\n"
        "```graph\n"
        '{"type":"function"}\n'
        "```\n"
    )
    out = strip_hand_sketch_filler(text)
    assert "How to Sketch" not in out
    assert "ASCII" not in out
    assert "Parabola at the origin." in out
    assert "```graph" in out


def test_strip_hand_sketch_filler_drops_mermaid_and_sketching_steps() -> None:
    text = (
        "Parabola at the origin.\n\n"
        "### Sketching Steps:\n"
        "1. Plot the vertex.\n\n"
        "### Mermaid Diagram (approximation):\n"
        "```mermaid\n"
        "graph LR\n"
        "    A --> B\n"
        "```\n\n"
        "```graph\n"
        '{"type":"function"}\n'
        "```\n"
    )
    out = strip_hand_sketch_filler(text)
    assert "Sketching Steps" not in out
    assert "Mermaid Diagram" not in out
    assert "Parabola at the origin." in out
    assert "```graph" in out


def test_strip_hand_sketch_filler_drops_sketching_tips() -> None:
    text = (
        "Parabola at the origin.\n\n"
        "### Sketching Tips:\n"
        "- Plot the vertex first\n\n"
        "```graph\n"
        '{"type":"function"}\n'
        "```\n"
    )
    out = strip_hand_sketch_filler(text)
    assert "Sketching Tips" not in out
    assert "Parabola at the origin." in out
    assert "```graph" in out


# --- One grammar (code-health audit DUP-03) ---------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        # The audit's case: a ``` line shown inside a ~~~ block is that block's content.
        "A fence starts with three backticks:\n\n~~~\n```python\n~~~\n\nThen write your code.",
        "````markdown\n```python\nx = 1\n```\n````",
        "> ```\n> code\n> ```",
        "Plain prose, no fence at all.",
    ],
)
def test_a_closed_reply_gets_no_stray_fence(text: str) -> None:
    assert close_unclosed_fences(text) == text


@pytest.mark.parametrize(
    ("text", "closer"),
    [
        ("```python\nprint(1)", "```"),
        ("````md\n```py\nx\n```", "````"),
        ("~~~\nstill open", "~~~"),
    ],
)
def test_an_open_fence_is_closed_by_its_own_run(text: str, closer: str) -> None:
    assert close_unclosed_fences(text) == f"{text}\n{closer}\n"


def test_a_same_run_opener_ends_a_forgotten_fence_in_model_text() -> None:
    text = '```graph\n{"x": 1\n```python\nprint(1)\n```'
    fences = list(iter_fences(text))
    assert [(f.lang, f.closed) for f in fences] == [("graph", False), ("python", True)]
    # Read strictly (CommonMark), the ```python line is the graph fence's content.
    assert [(f.lang, f.closed) for f in iter_fences(text, lenient=False)] == [("graph", True)]


def test_each_line_knows_its_fence() -> None:
    text = "a\n```py\nx\n```\nb\n~~~\n```\n~~~\nc"
    assert [fence is not None for fence in line_fences(text)] == [
        False, True, True, True, False, True, True, True, False,
    ]  # fmt: skip
