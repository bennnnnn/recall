# ruff: noqa: RUF001
"""Personal-data cue phrases for shipped locales (not user.locale-gated).

English classifiers already cover en. These phrases catch code-switching and
the app's seven other languages so projects / todos / calendar / email / memory
still opt into rich context.

Match with substring scans (no regex) on casefolded text.
"""

from __future__ import annotations

from typing import Literal

from app.core.validation import unify_devanagari

CueGroup = Literal[
    "projects",
    "todos",
    "calendar",
    "email",
    "memory",
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
        "meus projetos",
        "meu projeto",
        "os meus projetos",
        "мои проекты",
        "мой проект",
        "projelerim",
        "projelerimi",
        "የእኔ ፕሮጀክት",
        "ፕሮጀክቶች",
        "मेरे प्रोजेक्ट",
        "मेरा प्रोजेक्ट",
        "मेरी परियोजना",
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
        # Asking for or about a reminder, and "what do I have today": the list loads, so
        # a question is answered from it and an ask to add one gets the To-do button.
        "recuérdame",
        "recuerdame",
        "recordatorio",
        "tareas pendientes",
        "a mi lista",
        "de mi lista",
        "qué tengo hoy",
        "que tengo hoy",
        "qué tengo mañana",
        "que tengo mañana",
        "rappelle-moi",
        "rappelle moi",
        "un rappel",
        "à ma liste",
        "de ma liste",
        "qu'est-ce que j'ai aujourd'hui",
        "qu'est-ce que j'ai demain",
        "lembra-me",
        "lembre-me",
        "me lembra",
        "me lembre",
        "lembrete",
        "minhas tarefas",
        "à minha lista",
        "da minha lista",
        "o que tenho hoje",
        "o que eu tenho hoje",
        "напомни",
        "напоминани",
        "мои задачи",
        "мои дела",
        "список дел",
        "что у меня сегодня",
        "что у меня завтра",
        "hatırlat",
        "hatirlat",
        "görevlerim",
        "yapılacak",
        "listeme",
        "bugün neyim var",
        "yarın neyim var",
        "አስታውሰኝ",
        "አስታውሽኝ",
        "ማስታወሻ",
        "የሚደረጉ",
        "टू-डू",
        "मेरी सूची",
        "मेरी लिस्ट",
        "रिमाइंडर",
        "याद दिलाओ",
        "याद दिलाइए",
        "याद दिलाना",
        "याद दिला दो",
        "याद दिला देना",
        "आज मेरे पास क्या है",
        "कल मेरे पास क्या है",
        "आज मुझे क्या करना है",
    ),
    "calendar": (
        "mi calendario",
        "en mi agenda",
        "qué hay en mi calendario",
        "que hay en mi calendario",
        "mon calendrier",
        "mon agenda",
        "meu calendário",
        "meu calendario",
        "minha agenda",
        "мой календарь",
        "в календаре",
        "takvimim",
        "takvimimde",
        "ቀን መቁጠሪያ",
        "የእኔ ካላንደር",
        "मेरा कैलेंडर",
        "मेरे कैलेंडर",
    ),
    "email": (
        "mi correo",
        "mi bandeja",
        "revisa mi email",
        "revisa mi correo",
        "mes emails",
        "ma boîte mail",
        "ma boite mail",
        "minha caixa de entrada",
        "meu e-mail",
        "моя почта",
        "входящие",
        "gelen kutum",
        "e-postam",
        "የእኔ ኢሜይል",
        "የገቢ መልእክት",
        "मेरा ईमेल",
        "मेरे ईमेल",
        "मेरा इनबॉक्स",
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
        "o que você sabe sobre mim",
        "o que voce sabe sobre mim",
        "что ты помнишь",
        "что ты знаешь обо мне",
        "benim hakkımda ne biliyorsun",
        "benim hakkimda ne biliyorsun",
        "ምን ታስታውሳለህ",
        "ስለ እኔ ምን ታውቃለህ",
        "तुम्हें क्या याद है",
        "आपको क्या याद है",
        "मेरे बारे में क्या जानते",
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
        "o que eu deveria comer",
        "o que deveria comer",
        "o que comer hoje",
        "что поесть",
        "что приготовить",
        "ne yesem",
        "ne yemeliyim",
        "ምን ልብላ",
        "ምን ልልበስ",
        "मुझे क्या खाना चाहिए",
        "आज क्या खाऊँ",
        "आज क्या खाऊं",
        "क्या पहनूँ",
        "क्या पहनूं",
    ),
}

_ALL_GROUPS: tuple[CueGroup, ...] = (
    "projects",
    "todos",
    "calendar",
    "email",
    "memory",
)


def has_locale_cue(text: str, group: CueGroup) -> bool:
    """True when ``text`` contains a phrase from ``group`` (any shipped locale)."""
    folded = unify_devanagari(text).casefold()
    if not folded:
        return False
    return any(cue in folded for cue in _CUES[group])


def has_any_personal_locale_cue(text: str) -> bool:
    """True when any personal-data locale cue matches (code-switching OK)."""
    folded = unify_devanagari(text).casefold()
    if not folded:
        return False
    return any(cue in folded for group in _ALL_GROUPS for cue in _CUES[group])
