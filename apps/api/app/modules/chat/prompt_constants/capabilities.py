# ruff: noqa: RUF001
"""Capabilities / 'what can you do' overview — not a draft or layout demo."""

from app.modules.chat.prompt_constants.writing_kind import writing_request_kind
from app.services.text_normalize import collapse_ws

# Recall attaches real photos itself (a lookup that runs before the model).
PHOTO_LOOKUP_HINT = (
    "Recall shows real photos: when the user asks to see someone or something, the app "
    "looks up a photo and attaches it. Never say you can't display, show or send images "
    "or photos. If they asked for a photo and none came with this turn, say you couldn't "
    "find one this time and ask them to name the person or thing in full, in one short "
    "sentence. Never invent image links."
)

# The theme is the one setting a chat line changes (its card, settings_proposal); the
# model once offered "I can switch that for you" for the model, tone and language.
SETTINGS_IN_APP_HINT = (
    "Settings: from chat you can switch only the app theme (light, dark or the system's); "
    "the app adds a card for that. You cannot change any other setting: the model, tone, "
    "emoji, language, memory, voice or notifications. When asked, say in one short line "
    "where the user changes it (Settings → Models, Personalization, Language, Memory, "
    "Voice or Notifications), and never say you changed it. Writing differently in this "
    "chat (more casual, or in another language) needs no setting: just do it."
)

# Beside a message that names a setting: "use the pro model by default" got "Got it, I'll
# use the pro model by default" with the rule above only in the opening system message.
SETTINGS_ASK_REMINDER = (
    "If this message asks to change a setting, you cannot change it from chat (only the "
    "theme): say in one short line where in Settings the user changes it, and never say "
    "you changed it, switched it or will use it from now on."
)
_SETTING_WORDS = frozenset(
    {
        "model",
        "models",
        "tone",
        "emoji",
        "emojis",
        "language",
        "memory",
        "voice",
        "notifications",
        "setting",
        "settings",
        "default",
    }
)


def names_a_setting(text: str | None) -> bool:
    """True when ``text`` uses a word for one of the app's settings."""
    words = {word.strip(".,!?;:'\"").lower() for word in (text or "").split()}
    return bool(words & _SETTING_WORDS)


# Home-chip prompts (all shipped locales) plus short paraphrases.
_CAPABILITIES_EXACT = (
    "what can you help me with? give a few concrete examples.",
    "what can you do?",
    "what can you do",
    "en qué puedes ayudarme? dame algunos ejemplos concretos.",
    "qué puedes hacer?",
    "en quoi peux-tu m'aider ? donne quelques exemples concrets.",
    "que peux-tu faire ?",
    "wobei kannst du mir helfen? nenn ein paar konkrete beispiele.",
    "was kannst du?",
    "in cosa puoi aiutarmi? fammi qualche esempio concreto.",
    "cosa puoi fare?",
    "no que você pode me ajudar? dê alguns exemplos concretos.",
    "o que você pode fazer?",
    "чем ты можешь помочь? приведи несколько конкретных примеров.",
    "что ты умеешь?",
    "bana nasıl yardımcı olabilirsin? birkaç somut örnek ver.",
    "ne yapabilirsin?",
    "በምን ልረዳኝ ትችላለህ? ጥቂት ተጨባጭ ምሳሌዎችን ንገረኝ።",
    "ምን ማድረግ ትችላለህ?",
)

# Stems must sit near the start. Remainder after the stem is checked for a
# real task ("python", "this bug") vs an examples-ask / filler.
_CAPABILITIES_STEMS = (
    "what can you help me with",
    "what can you do",
    "how can you help me",
    "how can you help",
    "what do you help with",
    "what are you capable of",
    "what are your capabilities",
    "tell me what you can do",
    "what are you good at",
    "en qué puedes ayudarme",
    "en que puedes ayudarme",
    "qué puedes hacer",
    "que puedes hacer",
    "en quoi peux-tu m'aider",
    "que peux-tu faire",
    "wobei kannst du mir helfen",
    "was kannst du",
    "in cosa puoi aiutarmi",
    "cosa puoi fare",
    "no que você pode me ajudar",
    "no que voce pode me ajudar",
    "o que você pode fazer",
    "o que voce pode fazer",
    "чем ты можешь помочь",
    "что ты умеешь",
    "bana nasıl yardımcı olabilirsin",
    "bana nasil yardimci olabilirsin",
    "ne yapabilirsin",
    "በምን ልረዳኝ ትችላለህ",
    "ምን ማድረግ ትችላለህ",
)

_EXAMPLE_TAILS = (
    "give a few concrete examples",
    "give some concrete examples",
    "give a few examples",
    "give some examples",
    "dame algunos ejemplos concretos",
    "dame algunos ejemplos",
    "donne quelques exemples concrets",
    "donne quelques exemples",
    "nenn ein paar konkrete beispiele",
    "nenn ein paar beispiele",
    "fammi qualche esempio concreto",
    "fammi qualche esempio",
    "dê alguns exemplos concretos",
    "de alguns exemplos concretos",
    "dê alguns exemplos",
    "приведи несколько конкретных примеров",
    "приведи несколько примеров",
    "birkaç somut örnek ver",
    "birkac somut ornek ver",
    "birkaç örnek ver",
    "ጥቂት ተጨባጭ ምሳሌዎችን ንገረኝ",
)

_FILLER_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "me",
        "my",
        "please",
        "today",
        "now",
        "just",
        "really",
        "for",
        "to",
        "with",
        "about",
        "hey",
        "hi",
        "hello",
        "recall",
        "por",
        "favor",
        "s'il",
        "vous",
        "plait",
        "bitte",
        "per",
        "favore",
        "lütfen",
        "lutfen",
    }
)

_MAX_CAPABILITIES_CHARS = 240
_STEM_MAX_START = 40

CAPABILITIES_FORMAT_HINT = (
    "The user asked what Recall can help with. This is a capabilities overview, "
    "not a request to draft, chart, quiz, or draw anything.\n"
    "Shape like a ChatGPT capabilities list:\n"
    "  - One short opener, then 6-10 tight bullets. Each bullet starts with a "
    "**bold skill** and then 2-4 concrete examples in the same line.\n"
    "  - No ## headings, no nested lists, no cards, no tables, no blockquotes.\n"
    "  - End with 2-4 example prompts they can type, in bold.\n"
    "  - SHORT style: 4-5 bullets and skip the closer if needed.\n"
    "Content:\n"
    "  - Prefer their actual work from memory (projects, stack, "
    "job, apps they are building) for the examples. Do not dump email, "
    "location, or reminder contents. Do not say you "
    "looked at memory.\n"
    "  - Only claim shipped Recall abilities: conversation and reasoning, "
    "persistent memory, Schedule/reminders, camera and "
    "symbolic math, code help, writing/rewrites they copy and send, research "
    "and web search, photos, image generation (Pro).\n"
    "  - Recall does not connect to calendars or email inboxes. If they ask, "
    "say so plainly.\n"
    "  - Do not invent GitHub, banking, sending email/SMS, or any tool that is "
    "not in this prompt.\n"
    "  - Never emit ```email, ```sms, ```message, ```copy, ```chart, "
    "```geometry, ```graph, or ```mermaid on this turn — describe those in "
    "words. Do not interview and do not open a draft."
)


def _fold_capabilities_text(text: str) -> str:
    cleaned = collapse_ws(text).replace("\u2019", "'").replace("¿", "")
    return cleaned.casefold()


def _letters_and_spaces(text: str) -> str:
    """Replace punctuation with spaces in one pass (no regex)."""
    chars: list[str] = []
    for char in text:
        if char.isalnum() or char.isspace() or char in {"'", "-"}:
            chars.append(char)
        else:
            chars.append(" ")
    return collapse_ws("".join(chars))


def _strip_example_ask(rest: str) -> str:
    remaining = rest
    changed = True
    while changed:
        changed = False
        for tail in _EXAMPLE_TAILS:
            if remaining.startswith(tail):
                remaining = remaining[len(tail) :].strip()
                changed = True
            elif remaining.endswith(tail):
                remaining = remaining[: -len(tail)].strip()
                changed = True
    return remaining


def _remainder_is_examples_or_filler(rest: str) -> bool:
    stripped = _strip_example_ask(_letters_and_spaces(rest))
    if not stripped:
        return True
    return all(token in _FILLER_WORDS for token in stripped.split())


def is_capabilities_question(text: str) -> bool:
    """True for 'what can you do' overviews, including the Home chip prompt."""
    cleaned = collapse_ws(text)
    if not cleaned or len(cleaned) > _MAX_CAPABILITIES_CHARS:
        return False
    if writing_request_kind(cleaned) is not None:
        return False
    folded = _fold_capabilities_text(cleaned)
    folded_exact = _letters_and_spaces(folded)
    for exact in _CAPABILITIES_EXACT:
        if folded_exact == _letters_and_spaces(exact):
            return True
    for stem in _CAPABILITIES_STEMS:
        index = folded.find(stem)
        if index < 0 or index > _STEM_MAX_START:
            continue
        rest = folded[index + len(stem) :]
        if _remainder_is_examples_or_filler(rest):
            return True
    return False
