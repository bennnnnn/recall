"""A worked layout in the reply's language (live, 2026-11-15).

"Un coche acelera de 0 a 25 m/s en 5 s. ¿Cuál es su aceleración?" was worked in English under
Given, Required and Solution, only its follow-up questions in Spanish.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.modules.chat.finalize_passes import FINALIZE_PASSES
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.worked_language import WORKED_WORDS, layout_language, localized_working
from app.modules.chat.worked_render import WorkedLayout
from app.modules.chat.worked_solution import read_language
from app.modules.chat.worked_stream import ReplyFilter

_FIXTURE = Path(__file__).resolve().parents[6] / "docs" / "fixtures" / "worked_words.json"

SPANISH = "Un coche acelera de 0 a 25 m/s en 5 s. ¿Cuál es su aceleración?"

# As the server lays a worked block out (``worked_render``), then its card.
WORKED = "\n".join(
    [
        "**Given**  ",
        "$v_0 = 0\\,\\mathrm{m/s}$  ",
        "$t = 5\\,\\mathrm{s}$  ",
        "where $v_0$ = velocidad inicial, $t$ = tiempo",
        "",
        "**Required**  ",
        "$a$ (aceleración)",
        "",
        "**Solution**",
        "",
        "**Aceleración formula**  ",
        "$v = v_0 + a t$  ",
        "Solve for $a$  ",
        "$a = \\frac{v - v_0}{t}$",
        "",
        "**Substitution**  ",
        "$a = \\frac{25 - 0}{5}$",
        "",
        "**Answer**",
        "",
        "```answer",
        "verified: false",
        "**Given** stays: a card's body is not the layout",
        "```",
    ]
)


def test_the_table_is_the_fixtures_the_phone_reads() -> None:
    assert json.loads(_FIXTURE.read_text(encoding="utf-8")) == WORKED_WORDS


def test_a_spanish_layout_is_written_in_spanish() -> None:
    shown = localized_working(WORKED, "es")
    for line in (
        "**Datos**  ",
        "donde $v_0$ = velocidad inicial, $t$ = tiempo",
        "**Incógnita**  ",
        "**Solución**",
        "**Aceleración**  ",
        "Despejamos $a$  ",
        "**Sustitución**  ",
        "**Respuesta**",
    ):
        assert line in shown.split("\n")
    # The card is the answer's own fence: its body is never rewritten.
    assert "**Given** stays: a card's body is not the layout" in shown


@pytest.mark.parametrize("language", sorted(WORKED_WORDS))
def test_every_language_rewrites_every_heading(language: str) -> None:
    words = WORKED_WORDS[language]
    shown = localized_working(WORKED.replace("**Answer**", "**Answer (a)**"), language)
    if language == "en":
        assert shown == WORKED.replace("**Answer**", "**Answer (a)**")
        return
    for key in ("given", "required", "solution", "substitution"):
        assert f"**{words[key]}**" in shown
    assert f"**{words['answer']} (a)**" in shown


def test_a_reply_with_no_worked_layout_is_left_alone() -> None:
    text = "**Answer** first: the speed is 5 m/s.\n\nSolve for nothing here."
    assert localized_working(text, "es") == text


@pytest.mark.parametrize(
    ("line", "code"),
    [("language: es", "es"), ("Language: RU", "ru"), ("language: xx", None), ("given: es", None)],
)
def test_the_block_names_its_language(line: str, code: str | None) -> None:
    assert read_language(line) == code


def test_the_language_record_is_kept_and_never_drawn() -> None:
    """The model reads the message's language and names it; no word list does."""
    accum = StreamAccum()
    reply = ReplyFilter(accum, WorkedLayout(law_heading=True))
    block = "```worked\nlanguage: es\ngiven: t | 5 | s | tiempo\nanswer: a | 5 | m/s^2\n```\n"
    shown = reply.feed(block) + reply.flush()
    assert accum.worked_language == "es"
    assert "language" not in shown
    ctx = SimpleNamespace(
        worked_language=accum.worked_language, user=None, user_message_content=SPANISH
    )
    assert layout_language(cast(Any, ctx)) == "es"


def test_a_block_of_no_records_shows_its_lines_without_the_language() -> None:
    """With no record read, the block's own lines are shown; the language line is none of
    them (review, 2026-11-15)."""
    accum = StreamAccum()
    reply = ReplyFilter(accum, WorkedLayout())
    shown = reply.feed("```worked\nlanguage: es\nLa respuesta es 5.\n```\n") + reply.flush()
    assert "La respuesta es 5." in shown
    assert "language" not in shown


@pytest.mark.parametrize(
    ("message", "earlier", "instructions", "language"),
    [
        ("Как найти ускорение автомобиля?", [], None, "ru"),
        # No plain language of its own: the reply's words decide, never the app's alone.
        ("What voltage drives 2 A through a 15 Ω resistor?", [], None, "en"),
        ("2x + 3 = 7", [], None, "en"),
        # The reply-language note's own rule: a language named elsewhere is the user's choice.
        ("Как найти ускорение автомобиля?", [], "Always reply in English.", "en"),
        ("Как найти ускорение автомобиля?", ["reply in English from now on"], None, "en"),
    ],
)
def test_with_no_record_the_reply_language_rule_decides(
    message: str, earlier: list[str], instructions: str | None, language: str
) -> None:
    ctx = SimpleNamespace(
        worked_language=None,
        user=SimpleNamespace(locale="fr", custom_instructions=instructions),
        user_message_content=message,
        recent_messages=[SimpleNamespace(role="user", content=text) for text in earlier],
    )
    assert layout_language(cast(Any, ctx)) == language


def test_the_layout_is_written_in_its_language_last() -> None:
    """Every other pass reads the layout's English words (the card, the emoji, the lead)."""
    assert FINALIZE_PASSES[-1].name == "worked_language"
