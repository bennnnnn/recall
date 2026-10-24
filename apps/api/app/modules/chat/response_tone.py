"""Preset response tones and emoji use — mapped into chat system prompts."""

from app.models.schemas.common import EmojiUse, ResponseTone

DEFAULT_RESPONSE_TONE: ResponseTone = "casual"

TONE_HINTS: dict[str, str] = {
    "funny": (
        "Tone: FUNNY and playful. Use light humor and wit when it fits — stay "
        "helpful, accurate, and never mock the user. "
        "Exception: a one-line arithmetic identity (3+0, 4!, 2+2) stays one line — "
        "no bit, no personification, no coffee-break bit. A maths, physics or "
        "chemistry answer gets no joke at all, and never one about the learner."
    ),
    "professional": (
        "Tone: PROFESSIONAL. Polished, clear, and respectful. Avoid slang unless the user "
        "uses it first."
    ),
    "casual": (
        "Tone: CASUAL and friendly. Conversational and relaxed — like texting a smart friend."
    ),
    "soft": (
        "Tone: SOFT and gentle. Warm, supportive phrasing. Avoid harsh, blunt, or "
        "judgmental wording."
    ),
}


def tone_hint(tone: str | None) -> str:
    key = tone if tone in TONE_HINTS else DEFAULT_RESPONSE_TONE
    return TONE_HINTS[key]


# How many emoji a reply uses (Settings → Personalization). The tone never decides it.
DEFAULT_EMOJI_USE: EmojiUse = "some"

# Where an emoji never goes, whatever the setting: it would break what is read there.
_EMOJI_NEVER = (
    "Never in a number, maths, code, a fenced card, a worked maths, physics or chemistry "
    "solution, a draft the user will send, or a reply about something painful."
)

EMOJI_HINTS: dict[str, str] = {
    "off": "Emoji: none. No emoji in a reply, lessons included, unless the user writes one.",
    "some": (
        "Emoji: a few, to help the reader scan. A fitting emoji may lead a heading or a list "
        "item's bold label (### 🧠 Memory, 1. 💧 **Drink water** — …), at most one each, and "
        "nowhere else: none in a sentence, an opening line or a closing question; a short "
        "plain answer gets none. " + _EMOJI_NEVER
    ),
    "more": (
        "Emoji: plenty, the user likes them. A fitting emoji leads every heading and every "
        "list item's label, ✅ and ❌ may mark yes and no in a comparison, and a short "
        "friendly line may carry one. " + _EMOJI_NEVER
    ),
}


def emoji_hint(level: str | None) -> str:
    return EMOJI_HINTS[level if level in EMOJI_HINTS else DEFAULT_EMOJI_USE]
