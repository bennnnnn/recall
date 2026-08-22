"""Tests for app.services.speech."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways.speech_gateway import (
    openrouter_audio_format,
    pcm_to_wav,
    stream_pcm_via_openrouter,
)
from app.services.speech import (
    SPEECH_MAX_AUDIO_BYTES,
    TTS_FAST_ALIAS,
    TTS_QUALITY_ALIAS,
    iter_tts_pcm,
    normalize_tts_alias,
    resolve_tts_model,
    resolve_tts_voice,
    split_tts_lead,
    synthesize_speech,
    transcribe_audio,
)


@pytest.mark.asyncio
async def test_transcribe_returns_mock_when_mock_llm_enabled():
    settings = Settings(
        mock_llm_enabled=True,
        openrouter_api_key="",
        speech_transcription_enabled=True,
    )
    with patch("app.services.speech.mock_llm.should_mock_llm", return_value=True):
        text = await transcribe_audio(settings, b"fake-audio")
    assert text == "This is a mock transcription."


@pytest.mark.asyncio
async def test_transcribe_disabled_returns_none():
    settings = Settings(speech_transcription_enabled=False)
    assert await transcribe_audio(settings, b"fake-audio") is None


@pytest.mark.asyncio
async def test_transcribe_empty_payload_returns_none():
    settings = Settings(mock_llm_enabled=True, speech_transcription_enabled=True)
    assert await transcribe_audio(settings, b"") is None


@pytest.mark.asyncio
async def test_transcribe_rejects_over_shared_byte_cap():
    settings = Settings(mock_llm_enabled=True, speech_transcription_enabled=True)
    assert await transcribe_audio(settings, b"x" * (SPEECH_MAX_AUDIO_BYTES + 1)) is None


def test_openrouter_audio_format_from_filename():
    assert openrouter_audio_format("speech.m4a") == "m4a"
    assert openrouter_audio_format("clip.wav") == "wav"
    assert openrouter_audio_format("clip.mp4") == "m4a"


@pytest.mark.asyncio
async def test_transcribe_openrouter_json_api():
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_transcription_enabled=True,
        speech_transcription_model="openai/gpt-4o-mini-transcribe",
    )
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {"text": "hello there"}

    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.gateways.speech_gateway.get_pooled_client", return_value=client):
        text = await transcribe_audio(settings, b"audio-bytes", filename="speech.m4a")

    assert text == "hello there"
    call = client.post.call_args
    assert call.args[0] == "https://openrouter.ai/api/v1/audio/transcriptions"
    body = call.kwargs["json"]
    assert body["model"] == "openai/gpt-4o-mini-transcribe"
    assert body["input_audio"]["format"] == "m4a"


async def _transcribe_with_gateway_text(
    gateway_text: str | None, audio_bytes: bytes = b"short"
) -> str | None:
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_transcription_enabled=True,
        speech_transcription_model="openai/gpt-4o-mini-transcribe",
    )
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {"text": gateway_text}
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    with patch("app.gateways.speech_gateway.get_pooled_client", return_value=client):
        return await transcribe_audio(settings, audio_bytes, filename="speech.m4a")


@pytest.mark.asyncio
async def test_transcribe_filters_single_word_hallucination():
    assert await _transcribe_with_gateway_text("you") is None
    assert await _transcribe_with_gateway_text("You") is None
    assert await _transcribe_with_gateway_text("  bye  ") is None


@pytest.mark.asyncio
async def test_transcribe_filters_multiword_hallucination_when_audio_short():
    # "thank you" is two words → only filtered when audio is short (< 48 KB)
    assert await _transcribe_with_gateway_text("thank you", b"short") is None
    # Long audio keeps "thank you" (could be real speech)
    long_audio = b"x" * 60_000
    assert await _transcribe_with_gateway_text("thank you", long_audio) == "thank you"


@pytest.mark.asyncio
async def test_transcribe_keeps_real_speech():
    assert await _transcribe_with_gateway_text("hello there") == "hello there"
    assert await _transcribe_with_gateway_text("what is the weather") == "what is the weather"


@pytest.mark.asyncio
async def test_transcribe_keeps_none_and_empty():
    assert await _transcribe_with_gateway_text(None) is None
    assert await _transcribe_with_gateway_text("") is None


@pytest.mark.asyncio
async def test_synthesize_returns_mock_when_mock_llm_enabled():
    settings = Settings(
        mock_llm_enabled=True,
        openrouter_api_key="",
        speech_tts_enabled=True,
    )
    with patch("app.services.speech.mock_llm.should_mock_llm", return_value=True):
        result = await synthesize_speech(settings, "Hello world")
    assert result is not None
    audio, content_type = result
    assert content_type == "audio/mpeg"
    assert len(audio) > 0


@pytest.mark.asyncio
async def test_synthesize_disabled_returns_none():
    settings = Settings(speech_tts_enabled=False)
    assert await synthesize_speech(settings, "Hello") is None


@pytest.mark.asyncio
async def test_synthesize_empty_returns_none():
    settings = Settings(mock_llm_enabled=True, speech_tts_enabled=True)
    with patch("app.services.speech.mock_llm.should_mock_llm", return_value=True):
        assert await synthesize_speech(settings, "   ") is None


def test_resolve_tts_model_replaces_retired_openai_slug():
    settings = Settings(speech_tts_model="openai/gpt-4o-mini-tts")
    assert resolve_tts_model(settings) == "google/gemini-3.1-flash-tts-preview"
    assert resolve_tts_model(Settings(speech_tts_model="")) == (
        "google/gemini-3.1-flash-tts-preview"
    )
    assert (
        resolve_tts_model(Settings(speech_tts_model="openai/gpt-4o-mini-tts-2025-12-15"))
        == "google/gemini-3.1-flash-tts-preview"
    )
    assert resolve_tts_model(Settings(), alias=TTS_FAST_ALIAS) == "hexgrad/kokoro-82m"
    assert normalize_tts_alias(None) == TTS_QUALITY_ALIAS
    assert normalize_tts_alias("speech-tts-fast-model") == TTS_FAST_ALIAS


def test_resolve_tts_voice_maps_openai_voices_off_openai_models():
    settings = Settings(speech_tts_voice="alloy")
    assert resolve_tts_voice(settings, "google/gemini-3.1-flash-tts-preview") == "Kore"
    assert resolve_tts_voice(settings, "openai/gpt-4o-mini-tts") == "alloy"
    assert resolve_tts_voice(settings, "hexgrad/kokoro-82m") == "af_alloy"
    assert resolve_tts_voice(Settings(speech_tts_voice=""), "hexgrad/kokoro-82m") == ("af_alloy")


def test_pcm_to_wav_writes_riff_header():
    wav = pcm_to_wav(b"\x00\x00" * 8, sample_rate=24000, channels=1)
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"


@pytest.mark.asyncio
async def test_synthesize_openrouter_omits_language_field():
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_tts_enabled=True,
        speech_tts_model="",
        speech_tts_voice="alloy",
    )
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.content = b"\x00\x00" * 16
    response.text = ""
    response.headers = {"content-type": "audio/pcm;rate=24000;channels=1"}

    client = AsyncMock()
    client.post = AsyncMock(return_value=response)

    with (
        patch("app.services.speech.mock_llm.should_mock_llm", return_value=False),
        patch("app.gateways.speech_gateway.get_pooled_client", return_value=client),
    ):
        result = await synthesize_speech(settings, "Hello world", language="en-US")

    assert result is not None
    audio, content_type = result
    assert content_type == "audio/wav"
    assert audio[:4] == b"RIFF"
    body = client.post.call_args.kwargs["json"]
    assert client.post.call_args.args[0] == "https://openrouter.ai/api/v1/audio/speech"
    assert body["model"] == "google/gemini-3.1-flash-tts-preview"
    assert body["voice"] == "Kore"
    assert body["response_format"] == "pcm"
    assert "language" not in body
    assert "provider" not in body


@pytest.mark.asyncio
async def test_synthesize_kokoro_requests_mp3():
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_tts_enabled=True,
    )
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.content = b"ID3kokoro"
    response.text = ""
    response.headers = {"content-type": "audio/mpeg"}
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)

    with (
        patch("app.services.speech.mock_llm.should_mock_llm", return_value=False),
        patch("app.gateways.speech_gateway.get_pooled_client", return_value=client),
    ):
        result = await synthesize_speech(settings, "Hello", model_alias=TTS_FAST_ALIAS)

    assert result == (b"ID3kokoro", "audio/mpeg")
    body = client.post.call_args.kwargs["json"]
    assert body["model"] == "hexgrad/kokoro-82m"
    assert body["voice"] == "af_alloy"
    assert body["response_format"] == "mp3"


@pytest.mark.asyncio
async def test_synthesize_uses_openrouter_when_mock_llm_but_key_present():
    settings = Settings(
        mock_llm_enabled=True,
        openrouter_api_key="sk-or-test",
        speech_tts_enabled=True,
    )
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.content = b"ID3real-tts"
    response.text = ""
    response.headers = {"content-type": "audio/mpeg"}
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)

    with (
        patch("app.services.speech.mock_llm.should_mock_llm", return_value=True),
        patch("app.gateways.speech_gateway.get_pooled_client", return_value=client),
    ):
        result = await synthesize_speech(settings, "Hello")

    assert result == (b"ID3real-tts", "audio/mpeg")
    assert client.post.await_count == 1


@pytest.mark.asyncio
async def test_stream_pcm_yields_chunks_without_buffering():
    class _Resp:
        status_code = 200

        async def __aenter__(self) -> "_Resp":
            return self

        async def __aexit__(self, *args: object) -> bool:
            return False

        async def aiter_bytes(self, chunk_size: int = 4096):
            yield b"aa"
            yield b"bb"

    client = MagicMock()
    client.stream.return_value = _Resp()
    settings = Settings(openrouter_api_key="sk-or-test")
    chunks: list[bytes] = []
    with patch("app.gateways.speech_gateway.get_pooled_client", return_value=client):
        async for chunk in stream_pcm_via_openrouter(
            settings,
            "Hello",
            model="google/gemini-3.1-flash-tts-preview",
            voice="Kore",
        ):
            chunks.append(chunk)
    assert chunks == [b"aa", b"bb"]
    body = client.stream.call_args.kwargs["json"]
    assert body["response_format"] == "pcm"
    assert body["input"] == "Hello"


@pytest.mark.asyncio
async def test_iter_tts_pcm_mock_without_key():
    settings = Settings(
        mock_llm_enabled=True,
        openrouter_api_key="",
        speech_tts_enabled=True,
    )
    with patch("app.services.speech.mock_llm.should_mock_llm", return_value=True):
        chunks = [chunk async for chunk in iter_tts_pcm(settings, "Hello")]
    assert len(chunks) == 1
    assert len(chunks[0]) > 0


def test_split_tts_lead_keeps_short_text():
    assert split_tts_lead("Hello there.") == ("Hello there.", "")


def test_split_tts_lead_does_not_stop_after_one_word():
    rest_body = (
        "Here is a longer explanation that should stay in the lead until we "
        "have enough audio to cover the next request. Then this leftover "
        "paragraph is fetched only after playback has already started."
    )
    lead, rest = split_tts_lead(f"Sure. {rest_body}")
    assert lead.startswith("Sure.")
    assert len(lead) >= 120
    assert rest


def test_split_tts_lead_caps_the_window():
    lead, rest = split_tts_lead(f"{'alpha ' * 40}. Extra sentence after the cut.")
    assert len(lead) <= 160
    assert rest


@pytest.mark.asyncio
async def test_iter_tts_pcm_yields_lead_before_rest_finishes():
    import asyncio

    order: list[str] = []

    async def fake_stream(_settings: Settings, text: str, **_kwargs: object):
        if text.startswith("Lead"):
            order.append("lead-start")
            yield b"LEAD"
            order.append("lead-done")
            return
        order.append("rest-start")
        await asyncio.sleep(0.05)
        yield b"REST"
        order.append("rest-done")

    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_tts_enabled=True,
    )
    with (
        patch("app.services.speech.mock_llm.should_mock_llm", return_value=False),
        patch(
            "app.services.speech.split_tts_lead",
            return_value=("Lead sentence.", "Rest of the message."),
        ),
        patch(
            "app.services.speech.speech_gateway.stream_pcm_via_openrouter",
            fake_stream,
        ),
    ):
        chunks: list[bytes] = []
        async for chunk in iter_tts_pcm(settings, "unused"):
            chunks.append(chunk)
            if chunk == b"LEAD":
                order.append("yielded-lead")

    assert chunks == [b"LEAD", b"REST"]
    assert order.index("yielded-lead") < order.index("rest-done")
    assert "rest-start" in order
