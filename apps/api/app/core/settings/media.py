"""Voice (dictation, read-aloud, live talk) and image generation."""

from pydantic import BaseModel


class MediaSettings(BaseModel):
    speech_transcription_enabled: bool = True
    # Direct OpenAI voice. Empty overrides use the speech catalog aliases.
    speech_transcription_model: str = ""
    speech_rate_limit_per_minute: int = 10
    # Live dictation: the composer mic streams to an OpenAI transcription session over
    # WebRTC and the words land as they are spoken (``speech.dictation``). Off, or where
    # the phone has no WebRTC, it records a clip and uploads it to /speech/transcribe.
    speech_live_dictation_enabled: bool = True
    # Operator override (OpenAI model); empty → catalog alias `speech-dictation-model`.
    speech_dictation_model: str = ""
    # The phone stops a take at 45 s; the server hangs a dictation up this long + 15 s after
    # its connect whatever the phone does, so a mic left open cannot run up cost.
    speech_dictation_max_seconds: int = 45
    # Cloud TTS (read-aloud). Operator override (OpenAI model); empty →
    # catalog alias `speech-tts-model`.
    speech_tts_enabled: bool = True
    speech_tts_model: str = ""
    speech_tts_voice: str = ""
    # Turn-taking live voice: WebRTC + OpenAI gpt-realtime (not OpenRouter).
    # Its minutes allowance per plan is monthly_live_talk_minutes (plans.py).
    speech_live_talk_enabled: bool = True
    # Operator override (OpenAI model); empty → catalog alias `live-talk-model`.
    openai_realtime_model: str = ""
    speech_realtime_voice_enabled: bool = True
    # One session reserves up to this many seconds at mint (the phone hangs up
    # there), and a mint is refused when fewer than the minimum remain.
    live_talk_max_session_seconds: int = 900
    live_talk_min_session_seconds: int = 60

    image_generation_enabled: bool = True
    # Operator override (raw OpenRouter slug); empty → catalog alias
    # `image-gen-model`.
    image_generation_model: str = ""
