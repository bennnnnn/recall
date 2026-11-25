import pytest

from app.modules.speech.transcript_validation import sanitize_transcript


def test_sanitize_keeps_real_watching_phrase_on_enough_audio():
    text = sanitize_transcript("Thank you for watching.", audio_size=80_000)
    assert text == "Thank you for watching."


def test_sanitize_drops_watching_hallucination_on_tiny_clip():
    assert sanitize_transcript("thanks for watching!", audio_size=800) == ""


def test_sanitize_keeps_ordinary_dictation():
    assert sanitize_transcript("remind me to call mom", audio_size=800) == "remind me to call mom"


# Whisper's outros on a near-empty clip, in each language the recorded clip sends it.
_WHISPER_OUTROS = {
    "en": "Subtitles by the Amara.org community",
    "fr": "Sous-titres réalisés par la communauté d'Amara.org",
    "es": "Subtítulos realizados por la comunidad de Amara.org",
    "pt": "Legendas pela comunidade Amara.org",
    "ru": "Продолжение следует...",
    "tr": "İzlediğiniz için teşekkürler.",
}


@pytest.mark.parametrize("language", sorted(_WHISPER_OUTROS))
def test_sanitize_drops_whispers_outro_on_a_tiny_clip(language):
    assert sanitize_transcript(_WHISPER_OUTROS[language], audio_size=800) == ""


@pytest.mark.parametrize("language", sorted(_WHISPER_OUTROS))
def test_sanitize_keeps_the_outro_inside_real_speech(language):
    """Only a whole transcript is an outro: words around it are the user's."""
    text = f"Note this: {_WHISPER_OUTROS[language]} and call mom"
    assert sanitize_transcript(text, audio_size=800) == text


@pytest.mark.parametrize("language", sorted(_WHISPER_OUTROS))
def test_sanitize_keeps_the_outro_on_enough_audio(language):
    text = _WHISPER_OUTROS[language]
    assert sanitize_transcript(text, audio_size=80_000) == text
