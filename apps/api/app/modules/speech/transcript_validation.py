"""Reject classic STT hallucinations on weak/short clips.

Do not blacklist these phrases globally — a user may actually say them.
Only drop the transcript when the clip is too small to be real speech.
"""

from __future__ import annotations

# ~1-2s of compressed voice is larger than this; silence containers are not.
_WEAK_AUDIO_BYTES = 24_000

# Typical Whisper/YouTube outros on silence or fan noise, whole transcripts only: Whisper
# learned them from subtitled videos (Amara.org's credits, a series' "to be continued") and
# writes them on a near-empty clip in the language it was told. The recorded clip goes to
# Whisper in en/es/fr/pt/ru/tr, to OpenAI's transcribers in the rest.
_OUTROS = (
    # English
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "thanks for listening",
    "subscribe to my channel",
    "thank you for listening",
    "Subtitles by the Amara.org community",
    # French
    "Sous-titres réalisés par la communauté d'Amara.org",
    "Sous-titrage Société Radio-Canada",
    "Merci d'avoir regardé cette vidéo",
    # Spanish
    "Subtítulos realizados por la comunidad de Amara.org",
    "Subtítulos por la comunidad de Amara.org",
    "Gracias por ver el video",
    # Portuguese
    "Legendas pela comunidade Amara.org",
    "Legendas pela comunidade de Amara.org",
    "Obrigado por assistir",
    # Russian
    "Продолжение следует...",
    "Субтитры сделал DimaTorzok",
    "Субтитры создавал DimaTorzok",
    "Спасибо за просмотр",
    # Turkish
    "İzlediğiniz için teşekkür ederim",
    "İzlediğiniz için teşekkürler",
    "Altyazı M.K.",  # noqa: RUF001 - Turkish spells it with a dotless i
)


def _normalized_phrase(text: str) -> str:
    lowered = text.lower()
    chars: list[str] = []
    prev_space = True
    for char in lowered:
        if char.isalnum():
            chars.append(char)
            prev_space = False
        elif char.isspace():
            if not prev_space:
                chars.append(" ")
                prev_space = True
    return "".join(chars).strip()


_HALLUCINATION_PHRASES = frozenset(_normalized_phrase(phrase) for phrase in _OUTROS)


def sanitize_transcript(text: str, *, audio_size: int) -> str:
    """Return the transcript, or empty when it looks like a no-speech hallucination."""
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return ""
    if audio_size >= _WEAK_AUDIO_BYTES:
        return cleaned
    if _normalized_phrase(cleaned) in _HALLUCINATION_PHRASES:
        return ""
    return cleaned
