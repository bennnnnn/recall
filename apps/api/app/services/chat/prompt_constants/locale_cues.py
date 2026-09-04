# ruff: noqa: RUF001
"""Personal-data cue phrases for shipped locales (not user.locale-gated).

English classifiers already cover en. These phrases catch code-switching and
the other eight UI locales so projects / todos / calendar / email / memory /
learning still opt into rich context.

Match with substring scans (no regex) on casefolded text.
"""

from __future__ import annotations

from typing import Literal

CueGroup = Literal[
    "projects",
    "todos",
    "calendar",
    "email",
    "memory",
    "learning",
    "writing",
    "advice",
]

# Phrases are stored casefolded. Keep them specific enough to avoid matching
# generic English ("list", "mail") that the existing classifiers already own.
_CUES: dict[CueGroup, tuple[str, ...]] = {
    "projects": (
        "mis proyectos",
        "mi proyecto",
        "mes projets",
        "mon projet",
        "meine projekte",
        "mein projekt",
        "i miei progetti",
        "il mio progetto",
        "meus projetos",
        "meu projeto",
        "os meus projetos",
        "мои проекты",
        "мой проект",
        "projelerim",
        "projelerimi",
        "የእኔ ፕሮጀክት",
        "ፕሮጀክቶች",
    ),
    "todos": (
        "mis tareas",
        "mi lista",
        "mis recordatorios",
        "añade a la lista",
        "anade a la lista",
        "mes tâches",
        "mes taches",
        "ma liste",
        "mes rappels",
        "meine aufgaben",
        "meine liste",
        "meine erinnerungen",
        "le mie attività",
        "le mie attivita",
        "la mia lista",
        "i miei promemoria",
        "minhas tarefas",
        "minha lista",
        "meus lembretes",
        "мои задачи",
        "мой список",
        "мои напоминания",
        "yapılacaklar",
        "yapilacaklar",
        "hatırlatıcılarım",
        "hatirlaticilarim",
        "ተግባሮች",
        "የእኔ ዝርዝር",
        "ማስታወሻዎች",
    ),
    "calendar": (
        "mi calendario",
        "en mi agenda",
        "qué hay en mi calendario",
        "que hay en mi calendario",
        "mon calendrier",
        "mon agenda",
        "mein kalender",
        "meinen kalender",
        "il mio calendario",
        "meu calendário",
        "meu calendario",
        "minha agenda",
        "мой календарь",
        "в календаре",
        "takvimim",
        "takvimimde",
        "ቀን መቁጠሪያ",
        "የእኔ ካላንደር",
    ),
    "email": (
        "mi correo",
        "mi bandeja",
        "revisa mi email",
        "revisa mi correo",
        "mes emails",
        "ma boîte mail",
        "ma boite mail",
        "meine emails",
        "meinen posteingang",
        "la mia casella",
        "la mia email",
        "minha caixa de entrada",
        "meu e-mail",
        "моя почта",
        "входящие",
        "gelen kutum",
        "e-postam",
        "የእኔ ኢሜይል",
        "የገቢ መልእክት",
    ),
    "memory": (
        "qué recuerdas",
        "que recuerdas",
        "qué sabes de mí",
        "que sabes de mi",
        "sobre mí",
        "tu te souviens",
        "que sais-tu de moi",
        "que sais tu de moi",
        "was weißt du über mich",
        "was weisst du uber mich",
        "cosa sai di me",
        "o que você sabe sobre mim",
        "o que voce sabe sobre mim",
        "что ты помнишь",
        "что ты знаешь обо мне",
        "benim hakkımda ne biliyorsun",
        "benim hakkimda ne biliyorsun",
        "ምን ታስታውሳለህ",
        "ስለ እኔ ምን ታውቃለህ",
    ),
    "learning": (
        "mi vocabulario",
        "qué aprendí",
        "que aprendi",
        "mis palabras",
        "mon vocabulaire",
        "qu'ai-je appris",
        "mein vokabular",
        "il mio vocabolario",
        "meu vocabulário",
        "meu vocabulario",
        "мой словарный запас",
        "kelime dağarcığım",
        "kelime dagarcigim",
        "የእኔ ቃላት",
        "ምን ተማርኩ",
    ),
    "writing": (
        "escribeme un correo",
        "escríbeme un correo",
        "redacta un correo",
        "escribe un email",
        "escribe un correo",
        "écris un mail",
        "ecris un mail",
        "rédige un email",
        "redige un email",
        "schreib eine email",
        "schreib mir eine email",
        "scrivimi una email",
        "scrivi una email",
        "escreve um email",
        "escreva um e-mail",
        "escreva um email",
        "напиши письмо",
        "напиши email",
        "bir e-posta yaz",
        "bir email yaz",
        "ኢሜይል ጻፍ",
        "ደብዳቤ ጻፍ",
    ),
    "advice": (
        "qué debería comer",
        "que deberia comer",
        "qué como hoy",
        "que como hoy",
        "qué me recomiendas para cenar",
        "que me recomiendas para cenar",
        "que dois-je manger",
        "quoi manger ce soir",
        "was soll ich essen",
        "was soll ich anziehen",
        "cosa dovrei mangiare",
        "cosa mangiare stasera",
        "o que eu deveria comer",
        "o que deveria comer",
        "o que comer hoje",
        "что поесть",
        "что приготовить",
        "ne yesem",
        "ne yemeliyim",
        "ምን ልብላ",
        "ምን ልልበስ",
    ),
}

_ALL_GROUPS: tuple[CueGroup, ...] = (
    "projects",
    "todos",
    "calendar",
    "email",
    "memory",
    "learning",
    "writing",
)


def has_locale_cue(text: str, group: CueGroup) -> bool:
    """True when ``text`` contains a phrase from ``group`` (any shipped locale)."""
    folded = text.casefold()
    if not folded:
        return False
    return any(cue in folded for cue in _CUES[group])


def starts_with_locale_cue(text: str, group: CueGroup) -> bool:
    """True when a localized cue starts the request, not quoted later content."""
    folded = text.casefold().lstrip()
    if not folded:
        return False
    return any(
        folded == cue
        or (folded.startswith(cue) and folded[len(cue) : len(cue) + 1] in " \t,.:;!?¿¡")
        for cue in _CUES[group]
    )


def is_bare_locale_cue(text: str, group: CueGroup) -> bool:
    """True when a localized cue is the whole request, aside from punctuation.

    This distinguishes a bare ``escribeme un correo`` (ask what it should say)
    from ``escribeme un correo diciendo ...`` (the purpose is already present).
    A substring-only check cannot make that distinction and caused non-English
    draft requests to be interviewed after they had supplied the content.
    """
    folded = " ".join(text.casefold().split()).strip(".!?¿¡…،؟")
    if not folded:
        return False
    return any(folded == cue for cue in _CUES[group])


def has_any_personal_locale_cue(text: str) -> bool:
    """True when any personal-data locale cue matches (code-switching OK)."""
    folded = text.casefold()
    if not folded:
        return False
    return any(cue in folded for group in _ALL_GROUPS for cue in _CUES[group])
