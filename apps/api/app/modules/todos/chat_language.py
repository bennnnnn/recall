# ruff: noqa: RUF001 - the Turkish dotless i and the typographic apostrophe are matched words
"""Which chat messages may add or change to-dos: those written in English.

The server reads a chat to-do change against the user's own words (the time they
said, "mark it done", "remind me…"), and that reading is English. A message in
another language reads its to-dos in chat; adding or changing one happens in the
To-do screen, which the reply offers as a button (a ```todo_link fence).

A message counts as another language only on positive evidence: letters of another
script (Cyrillic, Ethiopic, …), or at least two words that only the app's other
Latin-script languages use. Any English to-do word keeps it English, so "remind me
to call Getachew ነገ at 10am" still saves.
"""

from __future__ import annotations

import re
import unicodedata

TODO_LINK_FENCE = "todo_link"

_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
# Words that put a to-do request in English, whatever else the message holds.
_ENGLISH_TODO = frozenset(
    {
        "remind",
        "reminder",
        "reminders",
        "to-do",
        "to-dos",
        "task",
        "tasks",
        "tomorrow",
        "today",
        "tonight",
        "add",
        "delete",
        "remove",
        "mark",
        "done",
        "schedule",
        "reschedule",
        "cancel",
        "uncheck",
        "complete",
        "move",
        "list",
        "every",
    }
)
# Words of Spanish, French, German, Italian, Portuguese and Turkish that English
# does not use: articles, pronouns, days, and the to-do and time words.
_OTHER_LATIN = frozenset(
    {
        # Spanish
        "el", "los", "las", "del", "que", "qué", "mañana", "manana", "hoy", "recuérdame",
        "recuerdame", "recordatorio", "recordatorios", "añade", "anade", "agrega", "agregar",
        "borra", "borrar", "elimina", "eliminar", "quita", "mis", "lista", "tarea", "tareas",
        "llamar", "tengo", "pendientes", "lunes", "martes", "miércoles", "jueves", "viernes",
        "sábado",
        # French
        "les", "des", "une", "demain", "aujourd'hui", "rappelle-moi", "rappelle", "rappel",
        "rappels", "ajoute", "ajouter", "supprime", "supprimer", "mes", "pour", "avec",
        "tâche", "tâches", "liste", "appeler", "lundi", "mardi", "mercredi", "jeudi",
        "vendredi", "samedi", "dimanche",
        # German
        "der", "das", "und", "eine", "morgen", "heute", "erinnere", "erinnerung",
        "erinnerungen", "füge", "hinzu", "lösche", "entferne", "mich", "meine", "für", "mit",
        "uhr", "aufgabe", "aufgaben", "anrufen", "montag", "dienstag", "mittwoch",
        "donnerstag", "freitag", "samstag", "sonntag",
        # Italian
        "il", "gli", "della", "che", "domani", "oggi", "ricordami", "promemoria", "aggiungi",
        "cancella", "mia", "mie", "mio", "miei", "alle", "attività", "chiamare", "lunedì",
        "martedì", "mercoledì", "giovedì", "venerdì", "domenica",
        # Portuguese
        "uma", "amanhã", "amanha", "hoje", "lembra-me", "lembre-me", "lembrete", "lembretes",
        "adiciona", "adicione", "apaga", "apague", "minha", "minhas", "meu", "meus", "às",
        "tarefa", "tarefas", "ligar", "terça", "quarta", "quinta", "sexta",
        # Turkish
        "yarın", "bugün", "hatırlat", "hatirlat", "hatırlatıcı", "hatırlatma", "ekle", "sil",
        "benim", "için", "saat", "görev", "görevler", "görevlerim", "listeme", "listeye",
        "beni", "bana", "pazartesi", "salı", "çarşamba", "perşembe", "cuma", "cumartesi",
    }
)  # fmt: skip
_OTHER_LATIN_WORDS = 2


def _other_script(text: str) -> bool:
    return any(char.isalpha() and not _is_latin(char) for char in text)


def _is_latin(char: str) -> bool:
    try:
        return unicodedata.name(char).startswith("LATIN")
    except ValueError:
        return False


def writes_todos_in_todo_screen(text: str | None) -> bool:
    """True when ``text`` is in another language: its to-do changes are made in To-do."""
    if not text or not text.strip():
        return False
    words = [word.casefold() for word in _WORD.findall(text)]
    if any(word in _ENGLISH_TODO for word in words):
        return False
    if _other_script(text):
        return True
    return len({word for word in words if word in _OTHER_LATIN}) >= _OTHER_LATIN_WORDS
