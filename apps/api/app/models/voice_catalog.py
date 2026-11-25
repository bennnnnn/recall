"""The voices Listen's models have, and which one plays a reply: what the user picks is
what they hear.

Settings → Voice has two pickers. "Live talk voice" (``users.tts_voice``) is a voice of
the realtime model. "Reply voice" (``users.reply_voice``) lists the voices of the model
that plays replies in the app's language (``picker_voices``): Kokoro's for English,
Spanish, French, Hindi and Portuguese, tts-1's for Russian, Turkish and Amharic. A reply in
that language plays in exactly the voice picked.

One swap remains, documented here and nowhere else: a reply in another language than the
app's (a Spanish answer in an English app), or in no clear language, plays in a voice of
that language's model, since a voice reads only its own language. It is the voice of the
same gender as the one picked (the first of that gender in the model's list, the best
rated), or the picked voice itself when that model has it too.

A user who never picked a reply voice hears the one their live talk voice gives: that voice
itself when the model has it (tts-1 has alloy, ash, coral, echo, sage and shimmer), else the
first of its gender.

Kokoro's voices are OpenRouter's list for hexgrad/kokoro-82m (``supported_voices`` of GET
/api/v1/models, 2026-11-24), the better rated of each language in hexgrad's own grades
(the VOICES file of hexgrad/Kokoro-82M on Hugging Face): no Santa voices, none graded D or
below in English. French has one voice. The phone holds the same lists
(``features/speech/model/voices.ts``); both are held to ``docs/fixtures/reply_voices.json``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.model_catalog import get, read_aloud_aliases


@dataclass(frozen=True)
class Voice:
    id: str
    female: bool


_F, _M = True, False

# tts-1's voices. It has none of marin, cedar, ballad or verse, which live talk has.
_OPENAI = (
    Voice("coral", _F),
    Voice("alloy", _F),
    Voice("nova", _F),
    Voice("sage", _F),
    Voice("shimmer", _F),
    Voice("ash", _M),
    Voice("echo", _M),
    Voice("fable", _M),
    Voice("onyx", _M),
)
_KOKORO = {
    "en": (
        Voice("af_heart", _F),
        Voice("af_bella", _F),
        Voice("af_nicole", _F),
        Voice("af_kore", _F),
        Voice("af_sarah", _F),
        Voice("bf_emma", _F),
        Voice("am_michael", _M),
        Voice("am_fenrir", _M),
        Voice("am_puck", _M),
        Voice("bm_george", _M),
    ),
    "es": (Voice("ef_dora", _F), Voice("em_alex", _M)),
    "fr": (Voice("ff_siwis", _F),),
    "hi": (Voice("hf_alpha", _F), Voice("hf_beta", _F), Voice("hm_omega", _M), Voice("hm_psi", _M)),
    "pt": (Voice("pf_dora", _F), Voice("pm_alex", _M)),
}
# Each Listen model's voices by the language they read, keyed by its catalog provider: a
# model that reads any language has one list, under "".
_BY_PROVIDER: dict[str, dict[str, tuple[Voice, ...]]] = {
    "openrouter": _KOKORO,
    "openai": {"": _OPENAI},
}
# The live talk voices tts-1 does not have, by gender, so a reply voice can follow them.
_LIVE_ONLY = (Voice("marin", _F), Voice("cedar", _M), Voice("ballad", _M), Voice("verse", _M))

REPLY_VOICE_IDS: frozenset[str] = frozenset(
    voice.id for voices in _BY_PROVIDER.values() for lists in voices.values() for voice in lists
)
_GENDER = {voice.id: voice.female for voices in (*_KOKORO.values(), _OPENAI, _LIVE_ONLY)
           for voice in voices}  # fmt: skip


def voices_of(alias: str, language: str | None) -> tuple[Voice, ...]:
    """The voices the Listen model ``alias`` reads ``language`` with."""
    by_language = _BY_PROVIDER.get(get(alias).provider, {})
    return by_language.get(language or "") or by_language.get("", ())


def picker_voices(language: str) -> tuple[Voice, ...]:
    """The Reply voice picker's list for an app language: the voices of the model that
    plays replies in it."""
    return voices_of(read_aloud_aliases(language)[0], language)


def voice_for(
    alias: str, language: str | None, reply_voice: str | None, live_voice: str | None
) -> str:
    """The voice model ``alias`` plays a text in ``language`` with, for a user who picked
    ``reply_voice`` (None: never) and ``live_voice`` for live talk."""
    return _pick(voices_of(alias, language), reply_voice, live_voice)


def reply_voice_for_app(language: str, reply_voice: str | None, live_voice: str | None) -> str:
    """The reply voice Settings shows for an app language: the one a reply in it plays."""
    return _pick(picker_voices(language), reply_voice, live_voice)


def _pick(voices: tuple[Voice, ...], reply_voice: str | None, live_voice: str | None) -> str:
    """The picked voice when ``voices`` has it; never picked, the live talk voice when it
    has that; else its first voice of the same gender (female when none is known)."""
    ids = [voice.id for voice in voices]
    if reply_voice in ids:
        return str(reply_voice)
    if reply_voice is None and live_voice in ids:
        return str(live_voice)
    female = _GENDER.get(reply_voice or "", _GENDER.get(live_voice or "", _F))
    return next((voice.id for voice in voices if voice.female == female), ids[0])
