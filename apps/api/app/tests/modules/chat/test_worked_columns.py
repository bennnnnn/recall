"""A question that writes its vectors as columns is answered in columns.

The owner's ball question (2026-11-25) gave its velocity as the column 5 over 2 and was
answered in î and ĵ. The turn reads the question's notation (``turn_reading.vector_notation``)
and tells the model to keep it (``WORKED_COLUMN_VECTORS_NOTE``); the layout writes a column's
unit beside it and rounds each entry by the card's rule.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.chat.prompt_constants.worked import (
    WORKED_BLOCK_CONTRACT,
    WORKED_COLUMN_VECTORS_NOTE,
)
from app.modules.chat.worked_render import WorkedLayout
from app.modules.chat.worked_stream import WorkedFilter
from app.modules.chat.worked_turn import (
    with_worked_contract,
    without_worked_contract,
    worked_layout,
)
from app.modules.physics.reply_policy import PHYSICS_VECTORS, physics_prompt_hints
from app.modules.turn_reading.vector_notation import writes_column_vectors
from app.services.column_vector import round_column
from app.tests.behavior.latex_check import latex_problems
from app.tests.modules.chat.test_verified_answer_card import _cards, _finalize

BALL = (
    "A ball of mass 500 g and velocity [ 5\n2] m/s bounces off a vertical wall. a) What is "
    "the impulse of the ball? b) The ball changes direction in 0.1 s. What is the force "
    "exerted by the wall on the ball?"
)

BALL_BLOCK = r"""```worked
language: en
given: m | 500 | g | mass of the ball | 0.5\,\mathrm{kg}
given: \vec{v}_i | \begin{pmatrix}5\\2\end{pmatrix} | m/s | velocity before the bounce
given: \vec{v}_f | \begin{pmatrix}-5\\2\end{pmatrix} | m/s | velocity after the bounce
given: \Delta t | 0.1 | s | time to change direction
required: \vec{I} | impulse of the ball
required: \vec{F} | force of the wall on the ball
part: a | Impulse of the ball
formula: Momentum | \vec{p} = m\vec{v}
substitution: \vec{p}_i = 0.5 \times \begin{pmatrix}5\\2\end{pmatrix} = \begin{pmatrix}2.5\\1\end{pmatrix}\,\mathrm{kg\,m/s}
substitution: \vec{p}_f = 0.5 \times \begin{pmatrix}-5\\2\end{pmatrix} = \begin{pmatrix}-2.5\\1\end{pmatrix}\,\mathrm{kg\,m/s}
formula: Impulse | \vec{I} = \vec{p}_f - \vec{p}_i
substitution: \vec{I} = \begin{pmatrix}-2.5\\1\end{pmatrix} - \begin{pmatrix}2.5\\1\end{pmatrix} = \begin{pmatrix}-5\\0\end{pmatrix}\,\mathrm{N\,s}
answer: \vec{I} | \begin{pmatrix}-5\\0\end{pmatrix} | N s
part: b | Force of the wall on the ball
formula: Average force | \vec{F} = \frac{\vec{I}}{\Delta t}
substitution: \vec{F} = \frac{1}{0.1}\begin{pmatrix}-5\\0\end{pmatrix} = \begin{pmatrix}-50.004\\12.3456\end{pmatrix}\,\mathrm{N}
answer: \vec{F} | \begin{pmatrix}-50.004\\12.3456\end{pmatrix} | N
```"""


@pytest.mark.parametrize(
    "message",
    [
        BALL,
        "A 2 kg cart moving with velocity [3; -1] m/s is struck.",
        "A force (4, -2)^T N acts for 3 s.",
        "A force [4, -2]ᵀ N acts for 3 s.",
        r"A velocity $\begin{pmatrix}5\\2\end{pmatrix}$ m/s.",
        r"A force $\begin{bmatrix} 4 \\ -2 \end{bmatrix}$ N acts for 3 s.",
        "Position ( 2\n -3 ) m at t = 0.",
        "a = ⎛ 3⎞\n⎝-1⎠",
    ],
)
def test_a_question_in_columns_is_read_as_columns(message: str) -> None:
    assert writes_column_vectors(message)


@pytest.mark.parametrize(
    "message",
    [
        "A ball of mass 0.5 kg and velocity (5i + 2j) m/s bounces off a wall.",
        "A 2 kg object's velocity changes from 3î + 4ĵ m/s to −2î + 6ĵ m/s.",
        "A ball hits a wall at 10 m/s at 30° to the normal.",
        "Find f on the interval [0, 5].",
        "The line through (2, 3) and (4, -1).",
        r"Find the determinant of $\begin{pmatrix}1 & 2\\3 & 4\end{pmatrix}$.",
        r"$\begin{vmatrix}3\\4\end{vmatrix}$",
        "See part (a)\nand part (b).",
        "What is 5 + 2?",
    ],
)
def test_other_notation_is_not_read_as_columns(message: str) -> None:
    assert not writes_column_vectors(message)


def test_a_question_in_columns_gets_the_note_and_loses_it_with_the_contract() -> None:
    layout = worked_layout(
        BALL,
        "physics",
        Settings(),
        answered=False,
        lightweight=False,
        several_requests=False,
    )
    assert layout is not None and layout.column_vectors
    prompt = [{"role": "user", "content": BALL}]
    with_contract = with_worked_contract(prompt, layout)
    contents = [message["content"] for message in with_contract]
    assert WORKED_BLOCK_CONTRACT in contents and WORKED_COLUMN_VECTORS_NOTE in contents
    assert with_contract[-1]["role"] == "user"
    assert without_worked_contract(with_contract) == prompt


def test_a_question_in_unit_vectors_gets_no_column_note() -> None:
    question = (
        "A 2 kg object's velocity changes from 3i + 4j m/s to -2i + 6j m/s. Find the impulse."
    )
    layout = worked_layout(
        question,
        "physics",
        Settings(),
        answered=False,
        lightweight=False,
        several_requests=False,
    )
    assert layout is not None and not layout.column_vectors
    contents = [
        m["content"] for m in with_worked_contract([{"role": "user", "content": "x"}], layout)
    ]
    assert WORKED_COLUMN_VECTORS_NOTE not in contents


def test_physics_asks_for_the_momentum_steps_in_the_questions_notation() -> None:
    assert PHYSICS_VECTORS in physics_prompt_hints(short=False)
    assert PHYSICS_VECTORS not in physics_prompt_hints(short=True)


def _laid_out(block: str) -> str:
    worked = WorkedFilter(WorkedLayout(law_heading=True, column_vectors=True))
    worked.feed(block)
    worked.close()
    return worked.text


def test_a_column_keeps_its_unit_and_each_entry_is_rounded_on_its_card() -> None:
    text = _laid_out(BALL_BLOCK)
    # The given's unit is written after its column, never dropped as a value in symbols.
    assert r"$\vec{v}_i = \begin{pmatrix}5\\2\end{pmatrix}\,\mathrm{m/s}$" in text
    # Each part's card: the column with its unit, each entry by the card's rule.
    assert r"$\begin{pmatrix}-5\\0\end{pmatrix}\,\text{N s}$" in text
    assert r"$\begin{pmatrix}-50.00\\12.35\end{pmatrix}\,\mathrm{N}$" in text
    assert "\\hat{i}" not in text
    assert latex_problems(text) == []


@pytest.mark.asyncio
async def test_the_saved_reply_keeps_each_column_card(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = await _finalize(monkeypatch, _laid_out(BALL_BLOCK), prompt=BALL)
    cards = _cards(saved)
    assert len(cards) == 2
    assert r"\begin{pmatrix}-5\\0\end{pmatrix}" in cards[0]
    assert r"\begin{pmatrix}-50.00\\12.35\end{pmatrix}" in cards[1]


# A part answering a column and a size, as the layout wrote it live (vector corpus, 2026-11-25).
MOMENTUM_LAID_OUT = (
    "**Given**  \n$m = 3\\,\\mathrm{kg}$  \n"
    "$\\vec{p} = \\begin{pmatrix}12\\\\-9\\end{pmatrix}\\,\\mathrm{kg\\,m/s}$\n\n"
    "**Required**  \n$\\vec{v}$ (velocity)  \n$v$ (speed)\n\n"
    "**Solution**\n\n**Momentum formula**  \n$\\vec{p} = m\\vec{v}$\n\n**Substitution**  \n"
    "$\\vec{v} = \\frac{1}{3}\\begin{pmatrix}12\\\\-9\\end{pmatrix}$  \n"
    "$\\vec{v} = \\begin{pmatrix}4\\\\-3\\end{pmatrix}\\ \\mathrm{m/s}$  \n"
    "$v = \\sqrt{4^2 + (-3)^2}$  \n$v = 5\\ \\mathrm{m/s}$\n\n**Answer**\n\n"
    "$\\begin{pmatrix}4\\\\-3\\end{pmatrix}\\,\\mathrm{m/s}$  \n$5\\,\\mathrm{m/s}$\n"
)


@pytest.mark.asyncio
async def test_a_column_beside_another_answer_is_on_the_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A column with a minus in it is one value, not working: it went above the card, which
    held the speed alone (vector corpus, 2026-11-25)."""
    asked = "A 3 kg body has momentum [ 12\n-9] kg m/s. Find its velocity and its speed."
    saved = await _finalize(monkeypatch, MOMENTUM_LAID_OUT, prompt=asked)
    cards = _cards(saved)
    assert len(cards) == 1
    assert r"\begin{pmatrix}4\\-3\end{pmatrix}" in cards[0]
    assert r"5\,\mathrm{m/s}" in cards[0]


@pytest.mark.parametrize(
    ("tex", "shown"),
    [
        (r"\begin{pmatrix}2.456\\-1\end{pmatrix}", r"\begin{pmatrix}2.46\\-1\end{pmatrix}"),
        (
            r"\begin{bmatrix} -50.0 \\ 12.3 \\ \end{bmatrix}",
            r"\begin{bmatrix}-50\\12.30\end{bmatrix}",
        ),
        (r"\begin{pmatrix}a\\2\end{pmatrix}", None),
        (r"\begin{pmatrix}1 & 2\\3 & 4\end{pmatrix}", None),
        (r"\begin{pmatrix}5\end{pmatrix}", None),
        ("2.5", None),
    ],
)
def test_round_column(tex: str, shown: str | None) -> None:
    from app.services.rounding_rule import number_latex

    assert round_column(tex, number_latex) == shown
