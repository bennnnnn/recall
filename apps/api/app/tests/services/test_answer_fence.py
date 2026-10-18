"""The answer-card protocol: the server's marker, and model answer fences."""

from __future__ import annotations

import pytest

from app.services.answer_fence import (
    VERIFIED_ANSWER_MARKER,
    answer_fence_value,
    demote_answer_fences,
    land_answer_card,
    mark_server_answer_fences,
    normalize_owned_fences,
    strip_forged_verified_markers,
    strip_model_simulation_fences,
    strip_verification_claims,
    verified_answer_fence,
)


@pytest.mark.parametrize(
    "reply",
    [
        "**Substitution**  \n$s = 3$\n\n**Answer**\n\n**Answer**\n",
        "**Substitution**  \n$s = 3$\n\n**Answer**\n\n**Answer:** $s = 37.5$\n",
    ],
)
def test_land_keeps_one_answer_heading_when_the_model_wrote_two(reply: str) -> None:
    # Physics follow-ups ("how far does it go?") showed **Answer** twice above the card.
    landed = land_answer_card(reply, "verified: true\n37.5")
    assert landed.count("**Answer**") == 1
    assert "**Answer**\n\n```answer\nverified: true\n37.5\n```" in landed


def test_the_server_card_opens_with_the_marker_once() -> None:
    card = verified_answer_fence("x = 6")
    assert card == "```answer\nverified: true\nx = 6\n```"
    assert verified_answer_fence("verified: true\nx = 6") == card
    chemistry = verified_answer_fence("notation: chemistry\npH = 2.00")
    assert chemistry == "```answer\nverified: true\nnotation: chemistry\npH = 2.00\n```"


def test_the_value_never_includes_header_lines() -> None:
    assert answer_fence_value("verified: true\nnotation: chemistry\npH = 2.00") == "pH = 2.00"
    assert answer_fence_value("label: answer\nverified: true\nx = 0") == "x = 0"


def test_marking_server_text_is_idempotent_and_keeps_layout() -> None:
    text = "**Answer**\n\n```answer\nx = 6\n```\n\nMore.\n"
    once = mark_server_answer_fences(text)
    assert once == "**Answer**\n\n```answer\nverified: true\nx = 6\n```\n\nMore.\n"
    assert mark_server_answer_fences(once) == once
    assert (
        mark_server_answer_fences("```answer\nx = 6\n```")
        == "```answer\nverified: true\nx = 6\n```"
    )


@pytest.mark.parametrize(
    "fence",
    [
        "```yaml\nverified: true\n```",
        "```python\nflags = {}\nverified: true\n```",
    ],
)
def test_a_marker_line_inside_code_the_user_asked_for_stays(fence: str) -> None:
    assert strip_forged_verified_markers(fence) == fence


def test_a_marker_line_outside_code_is_dropped() -> None:
    text = "Answer below.\nverified: true\n\n```text\nVERIFIED : true\nx = 7\n```"
    assert strip_forged_verified_markers(text) == "Answer below.\n\n```text\nx = 7\n```"


@pytest.mark.parametrize(
    ("variant", "lang"),
    [
        ("- Step:\n  ```answer\n  x = 7\n  ```", "answer"),
        ("~~~answer\nx = 7\n~~~", "answer"),
        ("````answer\nx = 7\n````", "answer"),
        ("``` answer\nx = 7\n```", "answer"),
        ("```Answer\nx = 7\n```", "answer"),
        ("```final extra words\nx = 7\n```", "final"),
        ("> ```result\n> x = 7\n> ```", "result"),
        ("~~~simulation\n{}\n~~~", "simulation"),
    ],
)
def test_every_spelling_normalizes_to_one_column_zero_fence(variant: str, lang: str) -> None:
    out = normalize_owned_fences(variant)
    body = "{}" if lang == "simulation" else "x = 7"
    assert f"```{lang}\n{body}\n```" in out


def test_other_fences_are_left_alone() -> None:
    text = "  ```python\n  print(1)\n  ```\n\n~~~graph\n{}\n~~~"
    assert normalize_owned_fences(text) == text


def test_an_answer_fence_nested_in_a_markdown_fence_is_content() -> None:
    text = "````markdown\n```answer\nx = 7\n```\n````"
    assert normalize_owned_fences(text) == text


def test_demoting_keeps_the_value_and_drops_the_header() -> None:
    text = "Weak acid.\n\n~~~answer\nnotation: chemistry\npH = 2.87\n~~~\n"
    assert demote_answer_fences(text) == "Weak acid.\n\npH = 2.87\n"


def test_a_model_simulation_is_dropped() -> None:
    assert strip_model_simulation_fences("Here.\n\n```simulation\n{}\n```") == "Here."
    assert strip_model_simulation_fences("```simulation\n{}\n```") == (
        "*Could not render that diagram.*"
    )


def test_claims_inside_code_are_untouched() -> None:
    text = "```python\nprint('verified with sympy')\n```"
    assert strip_verification_claims(text) == text


def test_marker_constant_matches_the_phone() -> None:
    assert VERIFIED_ANSWER_MARKER == "verified: true"


# --- land_answer_card: one card under one Answer heading ---------------------------------

_CARD = "```answer\nverified: true\nx = 3\n```"


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("Divide.\n\n**Answer:** $x = 3$", "Divide.\n\n**Answer**\n\n```answer\n$x = 3$\n```"),
        ("Divide.\n\n**Answer**:  $x = 3$  ", "Divide.\n\n**Answer**\n\n```answer\n$x = 3$\n```"),
        ("Divide.\n\nAnswer: x = 3", "Divide.\n\n**Answer**\n\n```answer\nx = 3\n```"),
        ("Divide.\n\n## Answer\n\n$x = 3$", "Divide.\n\n**Answer**\n\n```answer\n$x = 3$\n```"),
        ("**Answer**  \n- **$x = 3$**", "**Answer**\n\n```answer\n$x = 3$\n```"),
        ("**Answer**\n> $x = 3$\\", "**Answer**\n\n```answer\n$x = 3$\n```"),
    ],
)
def test_land_puts_the_value_under_the_heading_in_a_card(reply: str, expected: str) -> None:
    assert land_answer_card(reply, None) == expected


def test_land_moves_steps_above_the_heading_and_keeps_only_the_final_line() -> None:
    reply = (
        "**Formula**  \n$v = gt$\n\n**Answer**  \n$v = 9.8 \\times 2$  \n"
        "$v = 19.6\\ \\text{m/s}$\n\n**Check**  \n$19.6 / 9.8 = 2$"
    )
    out = land_answer_card(reply, None)
    assert out == (
        "**Formula**  \n$v = gt$\n\n$v = 9.8 \\times 2$  \n\n**Answer**\n\n"
        "```answer\n$v = 19.6\\ \\text{m/s}$\n```\n\n**Check**  \n$19.6 / 9.8 = 2$"
    )
    assert land_answer_card(out, None) == out


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (
            "**Answer**\n$x = 3$\nOnly the positive root counts.",
            "**Answer**\n\n```answer\n$x = 3$\n```\n\nOnly the positive root counts.",
        ),
        (
            "**Answer**\nx = 6 / 2\n\nx = 3",
            "x = 6 / 2\n\n**Answer**\n\n```answer\nx = 3\n```",
        ),
        ("**Answer**\n$x = 3$\n\n", "**Answer**\n\n```answer\n$x = 3$\n```\n\n"),
        ("**Answer**\n**x ≈ 1.5**", "**Answer**\n\n```answer\nx ≈ 1.5\n```"),
        (
            "**Answer**\nv = 9.8 × 2\nv ≈ 19.6 m/s",
            "v = 9.8 × 2\n\n**Answer**\n\n```answer\nv ≈ 19.6 m/s\n```",
        ),
        (
            "**Answer**\n\\[\nx = 3\n\\]\nOnly the positive root counts.",
            "**Answer**\n\n```answer\n$$\nx = 3\n$$\n```\n\nOnly the positive root counts.",
        ),
        (
            "**Answer**\n$$\n\\begin{cases} x = 1 \\\\\ny = 2\n\\end{cases}\n$$",
            "**Answer**\n\n```answer\n$$\n\\begin{cases} x = 1 \\\\\ny = 2\n\\end{cases}\n$$\n```",
        ),
        (
            "**Answer**\nA = 3 × 4\nArea = 12 cm²\nSo the area is 12 square centimetres.",
            "A = 3 × 4\n\n**Answer**\n\n```answer\nArea = 12 cm²\n```\n\n"
            "So the area is 12 square centimetres.",
        ),
        (
            "**Answer**\n2x + 3 = 7\n2x + 3 - 3 = 7 - 3\nx = 2",
            "2x + 3 = 7\n2x + 3 - 3 = 7 - 3\n\n**Answer**\n\n```answer\nx = 2\n```",
        ),
        (
            "**Answer:** $$\nx = 3\n$$\nOnly the positive root counts.",
            "**Answer**\n\n```answer\n$$\nx = 3\n$$\n```\n\nOnly the positive root counts.",
        ),
        ("**Answer**\n\n", "**Answer**\n\n"),
        (
            "**Answer:** $x = 2$\n$x = -2$",
            "**Answer**\n\n```answer\n$x = 2$, $x = -2$\n```",
        ),
        (
            "**Answer:** $x = 12 / 4$\n$x = 3$",
            "$x = 12 / 4$\n\n**Answer**\n\n```answer\n$x = 3$\n```",
        ),
    ],
)
def test_land_reads_only_maths_as_the_answer(reply: str, expected: str) -> None:
    assert land_answer_card(reply, None) == expected


@pytest.mark.parametrize(
    "answer",
    [
        "**Answer**\n$x = 3$",
        "**Answer:** $$\nx = 3\n$$",
        "**Answer**\n2x + 3 - 3 = 7 - 3\nx = 3",
        "**Answer**\nx = 6 / 2\nx ≈ 3",
        "**Answer**\n\\[\nx = 3\n\\]",
        "**Answer**\n**x ≈ 3**",
    ],
)
def test_land_keeps_a_sentence_after_the_verified_card(answer: str) -> None:
    out = land_answer_card(f"{answer}\nOnly the positive root counts.", "x = 3")
    assert out.endswith(f"**Answer**\n\n{_CARD}\n\nOnly the positive root counts.")
    assert out.count("$$") == 0
    assert "\\[" not in out and "\\]" not in out


@pytest.mark.parametrize("reply", ["**Answer**\nParis", "**Answer**\n\nA towel."])
def test_land_leaves_an_answer_that_is_not_maths(reply: str) -> None:
    assert land_answer_card(reply, None) == reply


def test_land_stops_at_a_bold_heading_line_but_not_at_a_bold_value() -> None:
    reply = "**Answer**\n$x^2 = 9$\n**x = 3**\n**Check** $3^2 = 9$"
    assert land_answer_card(reply, None) == (
        "$x^2 = 9$\n\n**Answer**\n\n```answer\nx = 3\n```\n\n**Check** $3^2 = 9$"
    )


def test_land_takes_a_display_block_as_one_value() -> None:
    reply = "**Answer**\n$x^2 = 9$\n$$\nx = \\pm 3\n$$"
    assert land_answer_card(reply, None) == (
        "$x^2 = 9$\n\n**Answer**\n\n```answer\n$$\nx = \\pm 3\n$$\n```"
    )


def test_land_replaces_the_model_value_with_the_verified_card() -> None:
    reply = "Steps.\n\n**Answer**\n$x^2 = 9$\n$x = \\pm 3$\n$x = 3$\n\nWant another?"
    out = land_answer_card(reply, "x = 3", above="The verified answer is $x = 3$.")
    assert out == (
        "Steps.\n\n$x^2 = 9$\n\nThe verified answer is $x = 3$.\n\n**Answer**\n\n"
        f"{_CARD}\n\nWant another?"
    )


def test_land_keeps_working_split_by_blank_lines_out_of_the_card() -> None:
    reply = "**Answer**\n\n$2x = 4$\n\n$x = 2$.\n\nWant another one?"
    assert land_answer_card(reply, None) == (
        "$2x = 4$\n\n**Answer**\n\n```answer\n$x = 2$\n```\n\nWant another one?"
    )


@pytest.mark.parametrize(
    ("roots", "card"),
    [
        ("- $x = 2$\n- $x = -2$", "$x = 2$, $x = -2$"),
        ("$x = \\frac{1}{2}$\n$x = -\\frac{1}{2}$", "$x = \\frac{1}{2}$, $x = -\\frac{1}{2}$"),
        ("$x = \\frac{-1}{2}$\n$x = \\frac{1}{2}$", "$x = \\frac{-1}{2}$, $x = \\frac{1}{2}$"),
        ("$x_1 = 2$\n$x_{2} = -2$", "$x_1 = 2$, $x_{2} = -2$"),
    ],
)
def test_land_keeps_every_root_in_the_card(roots: str, card: str) -> None:
    reply = f"**Answer**\n$x^2 = 4$\n{roots}\n\n**Check**\n$2^2 = 4$"
    assert land_answer_card(reply, None) == (
        f"$x^2 = 4$\n\n**Answer**\n\n```answer\n{card}\n```\n\n**Check**\n$2^2 = 4$"
    )


def test_land_leaves_a_card_that_already_follows_the_heading() -> None:
    reply = f"Steps.\n\n**Answer**\n\n{_CARD}"
    assert land_answer_card(reply, "x = 3") == reply
    assert land_answer_card(reply, None) == reply


def test_land_appends_a_verified_card_when_there_is_no_answer_section() -> None:
    assert land_answer_card("So $x = 3$.", "x = 3") == f"So $x = 3$.\n\n**Answer**\n\n{_CARD}"
    assert land_answer_card(f"So:\n\n{_CARD}", "x = 3") == f"So:\n\n{_CARD}"


def test_land_leaves_an_unverified_reply_without_an_answer_section() -> None:
    assert land_answer_card("So $x = 3$.", None) == "So $x = 3$."


@pytest.mark.parametrize(
    "reply",
    [
        "**Answer:** verified: true",
        "**Answer**\n$x = 3$\nverified: true",
        "**Answer:** label: answer\n\nverified: true",
    ],
)
def test_land_never_writes_a_header_line_into_an_unverified_card(reply: str) -> None:
    out = land_answer_card(reply, None)
    assert "```answer\nverified" not in out
    assert "```answer\nlabel" not in out


@pytest.mark.parametrize(
    "reply",
    [
        "Answer the question below in one line.\n\nWhat is $2 + 2$?",
        "**Answer** the questions in order.\n\n$x = 3$",
        "Answers: $x = 3$",
        "```markdown\n**Answer**\n$x = 3$\n```",
    ],
)
def test_land_leaves_text_that_is_not_an_answer_section(reply: str) -> None:
    assert land_answer_card(reply, None) == reply
