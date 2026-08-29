"""Preset response tones — mapped into chat system prompts."""

from typing import Literal

ResponseTone = Literal["funny", "professional", "casual", "soft"]

DEFAULT_RESPONSE_TONE: ResponseTone = "casual"

TONE_IDS: tuple[ResponseTone, ...] = ("funny", "professional", "casual", "soft")

TONE_HINTS: dict[str, str] = {
    "funny": (
        "Tone: FUNNY and playful. Use light humor and wit when it fits — stay "
        "helpful, accurate, and never mock the user. Do not add emoji. "
        "Exception: a one-line arithmetic identity (3+0, 4!, 2+2) stays one line — "
        "no bit, no personification, no coffee-break bit."
    ),
    "professional": (
        "Tone: PROFESSIONAL. Polished, clear, and respectful. Avoid slang and emoji "
        "unless the user uses them first."
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
