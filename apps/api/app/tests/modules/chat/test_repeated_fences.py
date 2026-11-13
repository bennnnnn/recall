"""A picture the reply repeats word for word is shown once.

The textbook run (2026-11-13) got its pie chart twice, with "%timeout" and a line of
Arabic and Chinese characters between the two copies.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.modules.chat.repeated_fences import drop_repeated_fences, drop_repeated_pictures

_PIE = (
    '```chart\n{"$schema":"https://vega.github.io/schema/vega-lite/v5.json","data":{"values":'
    '[{"method":"Walk","students":12},{"method":"Bus","students":42}]},"mark":{"type":"arc"}}\n```'
)
_QUESTION = "Draw a pie chart for how 120 students travel to school: walk 12, bus 42."


def test_the_copy_and_the_stray_tokens_between_go() -> None:
    reply = f"{_PIE} \n%timeout \n ذریع娱乐代理\n\n{_PIE}\n"
    out = drop_repeated_fences(reply, _QUESTION)
    assert out.count("```chart") == 1
    assert "timeout" not in out and "代理" not in out


@pytest.mark.parametrize(
    "between",
    ["Here is the same chart again, larger:", "The bus is the most common way to travel."],
)
def test_a_sentence_between_the_copies_stays(between: str) -> None:
    out = drop_repeated_fences(f"{_PIE}\n\n{between}\n\n{_PIE}", _QUESTION)
    assert out.count("```chart") == 1
    assert between in out


def test_a_copy_further_down_goes_and_the_text_around_it_stays() -> None:
    reply = f"Intro.\n\n{_PIE}\n\nThe walk share is 10%.\n\n{_PIE}\n\nThat is all."
    out = drop_repeated_fences(reply, _QUESTION)
    assert out.count("```chart") == 1
    assert "The walk share is 10%." in out and out.rstrip().endswith("That is all.")


@pytest.mark.parametrize(
    "reply",
    [
        # Two different charts.
        f"{_PIE}\n\n{_PIE.replace('42', '43')}",
        # The same code twice is the user's to have: only pictures are deduplicated.
        "```python\nprint(1)\n```\n\n```python\nprint(1)\n```",
        # One chart.
        f"Here:\n\n{_PIE}",
    ],
)
def test_other_replies_are_left_alone(reply: str) -> None:
    assert drop_repeated_fences(reply, _QUESTION) == reply


def test_stray_lines_in_another_reply_language_are_judged_by_its_script() -> None:
    question = "Нарисуй круговую диаграмму: пешком 12, автобус 42."
    reply = f"Вот диаграмма.\n\n{_PIE}\n娱乐代理\n{_PIE}"
    out = drop_repeated_fences(reply, question)
    assert out.count("```chart") == 1
    assert "娱乐" not in out and "Вот диаграмма." in out


@pytest.mark.parametrize("server_text", [False, True])
def test_a_server_reply_keeps_its_scene_under_each_part(server_text: bool) -> None:
    """A physics question in two parts gets the same scene under each part's card: the
    server's pictures are its own; only the model's repeats go."""
    reply = f"(a) 11.5 m\n\n{_PIE}\n\n(b) 1.53 s\n\n{_PIE}"
    state: Any = SimpleNamespace(
        server_text=server_text, text=reply, ctx=SimpleNamespace(user_message_content="")
    )
    kept = drop_repeated_pictures(cast(Any, state)).count("```chart")
    assert kept == (2 if server_text else 1)
