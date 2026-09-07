# ruff: noqa: RUF001
"""Capabilities / 'what can you do' overview — not a draft or layout demo."""

from app.services.chat.prompt_constants.routing import writing_request_kind
from app.services.text_normalize import collapse_ws

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
    "  - Prefer their actual work and learning from memory (projects, stack, "
    "job, apps they are building) for the examples. Do not dump email, "
    "location, calendar events, inbox, or reminder contents. Do not say you "
    "looked at memory.\n"
    "  - Only claim shipped Recall abilities: conversation and reasoning, "
    "persistent memory, Learning/vocabulary, Schedule/reminders, camera and "
    "symbolic math, code help, writing/rewrites they copy and send, research "
    "and web search, photos, image generation (Pro), Gmail and Google Calendar "
    "when connected.\n"
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
