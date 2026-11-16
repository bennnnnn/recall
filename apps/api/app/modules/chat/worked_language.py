# ruff: noqa: RUF001 - the Turkish dotless i is part of the words below
"""A worked layout in the language of the reply.

"Un coche acelera de 0 a 25 m/s en 5 s. ¿Cuál es su aceleración?" was worked in English, only
its follow-up questions in Spanish (live, 2026-11-15). The server writes a worked layout's
own words (Given, Required, Solution, Substitution, Steps, Answer, the ``where`` line, ``Solve
for``, a formula's "… formula" heading) in English only, and the ```worked block's contract
named no language, so the model wrote its records in English too.

The layout's language is the reply's, and the model names it: the block's first record is
``language: es``, the user's message's language, which every word of the block is in (a
model reads the message; no word list does). With no such record, it is
``reply_language.line_language``'s, as the formal reader's line is. The server's words are
written in it as the reply's last step, after every pass that reads them in English. The table
(``WORKED_WORDS``) and the phone's (``lib/markdown/workedWords.ts``), which lays the
headings out in any of these languages, are held to ``docs/fixtures/worked_words.json``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.modules.chat.reply_language import line_language
from app.services.md_fence_scan import line_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.turn_prep.context import StreamContext

# The server's words for a worked layout, by app language. "{symbol}" is the unknown's maths.
WORKED_WORDS: dict[str, dict[str, str]] = {
    "en": {
        "given": "Given",
        "required": "Required",
        "solution": "Solution",
        "substitution": "Substitution",
        "steps": "Steps",
        "answer": "Answer",
        "where": "where",
        "solve_for": "Solve for {symbol}",
    },
    "es": {
        "given": "Datos",
        "required": "Incógnita",
        "solution": "Solución",
        "substitution": "Sustitución",
        "steps": "Pasos",
        "answer": "Respuesta",
        "where": "donde",
        "solve_for": "Despejamos {symbol}",
    },
    "fr": {
        "given": "Données",
        "required": "Inconnue",
        "solution": "Solution",
        "substitution": "Application numérique",
        "steps": "Étapes",
        "answer": "Réponse",
        "where": "où",
        "solve_for": "On isole {symbol}",
    },
    "de": {
        "given": "Gegeben",
        "required": "Gesucht",
        "solution": "Lösung",
        "substitution": "Einsetzen",
        "steps": "Schritte",
        "answer": "Antwort",
        "where": "wobei",
        "solve_for": "Umstellen nach {symbol}",
    },
    "it": {
        "given": "Dati",
        "required": "Incognita",
        "solution": "Soluzione",
        "substitution": "Sostituzione",
        "steps": "Passaggi",
        "answer": "Risposta",
        "where": "dove",
        "solve_for": "Ricaviamo {symbol}",
    },
    "pt": {
        "given": "Dados",
        "required": "Incógnita",
        "solution": "Solução",
        "substitution": "Substituição",
        "steps": "Passos",
        "answer": "Resposta",
        "where": "onde",
        "solve_for": "Isolamos {symbol}",
    },
    "ru": {
        "given": "Дано",
        "required": "Найти",
        "solution": "Решение",
        "substitution": "Подстановка",
        "steps": "Шаги",
        "answer": "Ответ",
        "where": "где",
        "solve_for": "Выразим {symbol}",
    },
    "tr": {
        "given": "Verilenler",
        "required": "İstenen",
        "solution": "Çözüm",
        "substitution": "Yerine koyma",
        "steps": "Adımlar",
        "answer": "Yanıt",
        "where": "burada",
        "solve_for": "{symbol} yalnız bırakılır",
    },
    "am": {
        "given": "የተሰጠ",
        "required": "የሚፈለገው",
        "solution": "መፍትሄ",
        "substitution": "እሴቶቹን መተካት",
        "steps": "ደረጃዎች",
        "answer": "መልስ",
        "where": "እዚህ",
        "solve_for": "{symbol}ን ለብቻው ማውጣት",
    },
}

# The server's own English, as it writes it (``services/workout``, ``given_names``).
_HEADING = re.compile(
    r"^(?P<lead>[ \t]*)\*\*(?P<name>Given|Required|Solution|Substitution|Steps|Answer)"
    r"(?P<part> \([a-h]\))?(?P<colon>:?)\*\*(?P<tail>[ \t]*)$"
)
_FORMULA_HEADING = re.compile(
    r"^(?P<lead>[ \t]*)\*\*(?P<name>[^*\n]+) formula\*\*(?P<tail>[ \t]*)$"
)
_SOLVE_FOR = re.compile(r"^(?P<lead>[ \t]*)Solve for (?P<symbol>\$[^$\n]+\$)(?P<tail>[ \t]*)$")
_WHERE = re.compile(r"^(?P<lead>[ \t]*)where (?=\$)")
_OPENING = frozenset({"Given", "Required"})


def _line(line: str, words: dict[str, str]) -> str:
    heading = _HEADING.match(line)
    if heading is not None:
        name = words[heading.group("name").lower()]
        return (
            f"{heading.group('lead')}**{name}{heading.group('part') or ''}"
            f"{heading.group('colon')}**{heading.group('tail')}"
        )
    formula = _FORMULA_HEADING.match(line)
    if formula is not None:
        # A formula's name heads it alone: "… formula" is English word order.
        return f"{formula.group('lead')}**{formula.group('name')}**{formula.group('tail')}"
    solve = _SOLVE_FOR.match(line)
    if solve is not None:
        shown = words["solve_for"].format(symbol=solve.group("symbol"))
        return f"{solve.group('lead')}{shown}{solve.group('tail')}"
    return _WHERE.sub(lambda found: f"{found.group('lead')}{words['where']} ", line, count=1)


def localized_working(text: str, language: str) -> str:
    """``text`` with the server's worked-layout words in ``language``; a reply that is no
    worked layout (no **Given** or **Required** outside its fences), or one in English, as
    it is."""
    words = WORKED_WORDS.get(language)
    if words is None or language == "en" or "**" not in text:
        return text
    lines = text.split("\n")
    owners = line_fences(text)
    prose = [index for index, owner in enumerate(owners) if owner is None]
    if not any(
        (found := _HEADING.match(lines[index])) is not None and found.group("name") in _OPENING
        for index in prose
    ):
        return text
    for index in prose:
        lines[index] = _line(lines[index], words)
    return "\n".join(lines)


def layout_language(ctx: StreamContext) -> str:
    """The language a reply's worked layout is written in: the one its ```worked block
    named, else the message's own when it is plainly one of the app's, else the app's."""
    if ctx.worked_language in WORKED_WORDS:
        return ctx.worked_language
    locale = ctx.user.locale if ctx.user is not None else None
    return line_language(ctx.user_message_content or "", locale)


def localize_working_pass(state: FinalizeState) -> str:
    """The finalize pass: the layout's words in the reply's language, read last."""
    return localized_working(state.text, layout_language(state.ctx))
