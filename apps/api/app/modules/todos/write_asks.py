# ruff: noqa: RUF001 - Turkish dotless i and Cyrillic letters are matched words
"""Which messages ask chat to add or change a to-do, in any language.

Chat only reads to-dos (owner, 2026-11-27): they are added and changed in the To-do
screen. Asked to add one, a model still asked "¿cuándo?" and then wrote "He añadido…",
so such a request is answered by the server: one line in the user's language and the Open
To-do button, no model call. English is read by ``write_asks_english``, Hindi by
``write_asks_hindi``.

In the other languages a request is a reminder phrase ("recuérdame", "напомни"), or an add or delete
verb beside a to-do target ("añade … a mis tareas"). Words with an everyday
meaning stay out: Spanish "tarea" (also homework), "todo" (all), "pon" (play) and
"marca" (brand), French "note" (a grade), Russian "задача" (a maths problem),
Amharic "ዝርዝር" (also details), Hindi "काम" (work) and a bare "सूची" (any list),
German "ich erinnere mich" (I remember). After the button, a reply with a time or a yes
("a las 5", "sí", "हाँ") asks the same thing again; a question is a new one.

German and Italian are no app language, but a message in either still asks for a to-do
change chat must not make (``chat_language``), so their words stay: they read the request,
they write nothing in those languages.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.core.validation import unify_devanagari
from app.modules.todos.chat_language import (
    answer_language,
    message_language,
    reads_as_english,
    todo_screen_answer,
)
from app.modules.todos.reply_offers import asked_about_a_change, follows_todo_reply
from app.modules.todos.spoken_when import is_only_a_when
from app.modules.todos.write_asks_english import asks_in_english
from app.modules.todos.write_asks_hindi import asks_in_hindi
from app.modules.turn_reading.routing import is_short_confirmation

# A phrase ending in "*" matches the start of a word (Turkish and Amharic add endings).
_REMIND = (
    # Spanish
    "recuérdame", "recuerdame", "recordarme", "pon un recordatorio",
    # French
    "rappelle-moi", "rappelez-moi", "fais-moi penser",
    # Italian
    "ricordami", "ricordarmi",
    # Portuguese
    "lembra-me", "lembre-me", "lembrar-me", "me lembra de", "me lembre de",
    # Turkish
    "hatırlat", "hatirlat", "hatırlatır mısın", "hatirlatir misin",
    # Russian
    "напомни", "напомните",
    # Amharic
    "አስታውሰኝ", "አስታውሺኝ", "አስታውሱኝ",
)  # fmt: skip
_ADD_OR_CHANGE = (
    "añade", "anade", "añadir", "agrega", "agregar", "apunta", "anota", "borra", "borrar",
    "elimina", "eliminar", "quita",
    "ajoute", "ajouter", "ajoutez", "mets", "supprime", "supprimer", "enlève", "enleve",
    "retire",
    "füge", "fuge", "trag", "trage", "lösche", "losche", "löschen", "entferne", "setz",
    "aggiungi", "aggiungere", "metti", "cancella", "elimina", "togli", "rimuovi",
    "adiciona", "adicione", "adicionar", "coloca", "coloque", "põe", "anote", "apaga",
    "apague", "remove", "remova", "exclui", "exclua",
    "ekle", "sil", "kaldır", "kaldir",
    "добавь", "добавьте", "запиши", "запишите", "удали", "удалите", "убери",
    "ጨምር", "ጨምሪ", "ጨምሩ", "ሰርዝ", "ሰርዢ", "አስገባ",
)  # fmt: skip
_TODO_TARGET = (
    "mis tareas", "a tareas", "en tareas", "mi lista", "lista de tareas", "mis pendientes",
    "lista de pendientes", "recordatorio", "recordatorios",
    "ma liste", "mes tâches", "mes taches", "liste de tâches", "rappel", "rappels",
    "meine liste", "meiner liste", "meine aufgaben", "meinen aufgaben", "aufgabenliste", "erinnerung", "erinnerungen",
    "la mia lista", "mia lista", "le mie attività", "le mie attivita", "promemoria",
    "minha lista", "minhas tarefas", "lista de tarefas", "lembrete", "lembretes",
    "listeme", "listeye", "listemden", "görevlerime", "yapılacaklar*", "yapilacaklar*",
    "мой список", "в список", "список дел", "мои задачи", "в задачи", "напоминание",
    "напоминания",
    "ዝርዝሬ*", "ተግባሮቼ*", "የሚደረጉ*",
    "to-do",
)  # fmt: skip
# German "erinnere mich" (remind me), never "ich erinnere mich" (I remember).
_GERMAN_REMIND_RE = re.compile(r"(?<!ich )(?<![\w'-])erinnere? mich(?![\w'-])")
# A time or a yes, answering the To-do button's turn again; a question is a new one.
_DIGIT = re.compile(r"\d")
_YES_OR_DAY = (
    "sí", "si", "oui", "ja", "sì", "sim", "evet", "да", "አዎ",
    "mañana", "manana", "demain", "morgen", "domani", "amanhã", "amanha", "yarın", "yarin",
    "завтра", "ነገ", "hoy", "aujourd'hui", "heute", "oggi", "hoje", "bugün", "сегодня", "ዛሬ",
    "हाँ", "हां", "जी हाँ", "जी हां", "ठीक है", "कल", "आज", "परसों", "सोमवार", "मंगलवार",
    "बुधवार", "गुरुवार", "बृहस्पतिवार", "शुक्रवार", "शनिवार", "रविवार",
)  # fmt: skip


# A word's letters: ``\w`` and Devanagari's vowel signs, which ``\w`` leaves out, so "कल"
# (tomorrow) is not the start of "कला" (art). Not the danda, a full stop.
_IN_WORD = r"[\w'\-\u0900-\u0963\u0966-\u097f]"


def _pattern(phrases: Iterable[str]) -> re.Pattern[str]:
    parts = [
        re.escape(phrase[:-1]) if phrase.endswith("*") else re.escape(phrase) + f"(?!{_IN_WORD})"
        for phrase in phrases
    ]
    return re.compile(f"(?<!{_IN_WORD})(?:" + "|".join(parts) + ")")


_REMIND_RE = _pattern(_REMIND)
_ADD_OR_CHANGE_RE = _pattern(_ADD_OR_CHANGE)
_TODO_TARGET_RE = _pattern(_TODO_TARGET)
_YES_OR_DAY_RE = _pattern(_YES_OR_DAY)


def asks_to_change_todos(text: str | None, *, prior_assistant: str | None = None) -> bool:
    """True when ``text`` asks to add, change or delete a to-do.

    ``prior_assistant`` is the reply before it: after the To-do button, an old reminder
    card or a question offering one, a time or a yes is that request ("6pm", "a las 5",
    "sí", "yes"). The other languages' words
    are read only in a message English does not claim: "how do I remove a to-do in React"
    is English, whatever "remove" means in Portuguese.
    """
    if asks_in_english(text):
        return True
    english = reads_as_english(text)
    folded = " ".join(unify_devanagari(text or "").casefold().split())
    if not folded:
        return False
    if follows_todo_reply(prior_assistant) and "?" not in folded:
        if is_only_a_when(text):
            return True
        # A yes to an offer of a reminder; after the button, "ok" only says it was read.
        if asked_about_a_change(prior_assistant) and is_short_confirmation(text or ""):
            return True
        # "a las 5", "sí, mañana", "हाँ, कल": a time or a yes in one of the other languages.
        said = message_language(text) is not None
        if said and (_DIGIT.search(folded) or _YES_OR_DAY_RE.search(folded)):
            return True
    if english:
        return False
    if _REMIND_RE.search(folded) or _GERMAN_REMIND_RE.search(folded):
        return True
    if asks_in_hindi(folded):
        return True
    return bool(_ADD_OR_CHANGE_RE.search(folded) and _TODO_TARGET_RE.search(folded))


def todo_screen_reply(
    text: str | None,
    *,
    prior_user: str | None = None,
    prior_assistant: str | None = None,
    locale: str | None = None,
) -> str | None:
    """The server's whole reply to a to-do change asked in chat, else None."""
    if not asks_to_change_todos(text, prior_assistant=prior_assistant):
        return None
    return todo_screen_answer(answer_language(text, prior_user=prior_user, locale=locale))
