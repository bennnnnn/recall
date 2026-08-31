"""Tests for app.services.speech."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways.speech_gateway import (
    live_talk_chat_payload,
    openai_input_audio_format,
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


def test_openai_input_audio_format_sniffs_wav_not_m4a():
    wav = pcm_to_wav(b"\x00\x00" * 16)
    assert openai_input_audio_format("speech.m4a", wav) == "wav"
    assert openai_input_audio_format("speech.mp3", b"ID3" + b"\x00" * 8) == "mp3"
    assert openai_input_audio_format("speech.m4a", b"\x00\x00ftyp") is None
    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 8
    assert openai_input_audio_format("speech.wav", mp4) is None
    assert openai_input_audio_format("speech.mp3", mp4) is None


def test_live_talk_chat_payload_streams_pcm16():
    wav = pcm_to_wav(b"\x00\x00" * 16)
    payload = live_talk_chat_payload(wav, filename="speech.wav", model="openai/gpt-audio-mini")
    assert payload is not None
    assert payload["stream"] is True
    assert payload["audio"] == {"voice": "alloy", "format": "pcm16"}
    user = payload["messages"][1]
    assert isinstance(user, dict)
    content = user["content"]
    assert isinstance(content, list)
    part = content[0]
    assert isinstance(part, dict)
    input_audio = part["input_audio"]
    assert isinstance(input_audio, dict)
    assert input_audio["format"] == "wav"
    assert live_talk_chat_payload(b"not-audio", filename="speech.m4a", model="x") is None


def test_live_talk_chat_payload_includes_recent_text():
    wav = pcm_to_wav(b"\x00\x00" * 16)
    payload = live_talk_chat_payload(
        wav,
        filename="speech.wav",
        model="openai/gpt-audio-mini",
        history=[("user", "what is 2+2"), ("assistant", "4")],
    )
    assert payload is not None
    messages = payload["messages"]
    assert isinstance(messages, list)
    assert messages[1] == {"role": "user", "content": "what is 2+2"}
    assert messages[2] == {"role": "assistant", "content": "4"}


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
    assert "language" not in body


@pytest.mark.asyncio
async def test_transcribe_openrouter_sends_language_hint():
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_transcription_enabled=True,
        speech_transcription_model="openai/gpt-transcribe",
    )
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {"text": "hello there"}

    client = AsyncMock()
    client.post = AsyncMock(return_value=response)

    with patch("app.gateways.speech_gateway.get_pooled_client", return_value=client):
        text = await transcribe_audio(
            settings,
            b"audio-bytes",
            filename="speech.m4a",
            language="en-US",
        )

    assert text == "hello there"
    body = client.post.call_args.kwargs["json"]
    assert body["model"] == "openai/gpt-transcribe"
    assert body["language"] == "en"


@pytest.mark.asyncio
async def test_transcribe_drops_watching_hallucination_on_tiny_clip():
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_transcription_enabled=True,
        speech_transcription_model="openai/gpt-transcribe",
    )
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {"text": "Thank you for watching!"}

    client = AsyncMock()
    client.post = AsyncMock(return_value=response)

    with patch("app.gateways.speech_gateway.get_pooled_client", return_value=client):
        text = await transcribe_audio(settings, b"tiny", filename="speech.m4a")

    assert text == ""


@pytest.mark.asyncio
async def test_transcribe_openrouter_empty_text_is_success():
    """Silence is a valid STT result — not a provider failure."""
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_transcription_enabled=True,
        speech_transcription_model="openai/gpt-transcribe",
    )
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = {"text": ""}

    client = AsyncMock()
    client.post = AsyncMock(return_value=response)

    with patch("app.gateways.speech_gateway.get_pooled_client", return_value=client):
        text = await transcribe_audio(settings, b"silence-m4a", filename="speech.m4a")

    assert text == ""


@pytest.mark.asyncio
async def test_transcribe_openrouter_http_error_is_none():
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_transcription_enabled=True,
    )
    response = MagicMock()
    response.status_code = 502
    response.text = "upstream down"
    response.raise_for_status.side_effect = Exception("502")

    client = AsyncMock()
    client.post = AsyncMock(return_value=response)

    with patch("app.gateways.speech_gateway.get_pooled_client", return_value=client):
        text = await transcribe_audio(settings, b"audio-bytes", filename="speech.m4a")

    assert text is None


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


def test_parse_audio_sse_delta_reads_stream_chunks():
    from app.gateways.speech_gateway import parse_audio_sse_delta

    audio, text = parse_audio_sse_delta(
        {"choices": [{"delta": {"audio": {"data": "YWJj", "transcript": "Hi"}}}]}
    )
    assert audio == "YWJj"
    assert text == "Hi"


def test_parse_audio_sse_delta_falls_back_to_content():
    from app.gateways.speech_gateway import parse_audio_sse_delta

    audio, text = parse_audio_sse_delta({"choices": [{"delta": {"content": "Hello"}}]})
    assert audio == ""
    assert text == "Hello"


def test_merge_stream_transcript_cumulative_or_incremental():
    from app.gateways.speech_gateway import merge_stream_transcript

    assert merge_stream_transcript("Hi", "Hi there") == "Hi there"
    assert merge_stream_transcript("Hi", " there") == "Hi there"
    assert merge_stream_transcript("Hi there", "there") == "Hi there"


def test_decode_audio_b64_incremental_keeps_remainder():
    from app.gateways.speech_gateway import decode_audio_b64_incremental

    pcm, rest = decode_audio_b64_incremental("", "aG")
    assert pcm == b""
    assert rest == "aG"
    pcm, rest = decode_audio_b64_incremental(rest, "VsbG8=")
    assert pcm == b"hello"
    assert rest == ""


def test_decode_joined_audio_b64():
    from app.gateways.speech_gateway import decode_joined_audio_b64

    raw = decode_joined_audio_b64(["aGVs", "bG8="])
    assert raw == b"hello"


@pytest.mark.asyncio
async def test_speech_to_speech_mock_without_key():
    from app.services.speech import speech_to_speech

    settings = Settings(
        mock_llm_enabled=True,
        openrouter_api_key="",
        speech_live_talk_enabled=True,
    )
    with patch("app.services.speech.mock_llm.should_mock_llm", return_value=True):
        result = await speech_to_speech(settings, b"fake-audio")
    assert result is not None
    audio, content_type, transcript = result
    assert content_type == "audio/wav"
    assert audio[:4] == b"RIFF"
    assert transcript.startswith("This is a mock")


@pytest.mark.asyncio
async def test_iter_speech_to_speech_emits_clip_before_stream_ends():
    from app.services.live_talk_stream import iter_speech_to_speech

    wav = pcm_to_wav(b"\x00\x00" * 16)
    order: list[str] = []

    async def fake_gateway(*_args: object, **_kwargs: object):
        order.append("first-pcm")
        yield (10_000).to_bytes(2, "little", signed=True) * 30_000, "Hi"
        order.append("rest-pcm")
        yield (10_000).to_bytes(2, "little", signed=True) * 1_000, "Hi there"

    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_live_talk_enabled=True,
        speech_transcription_enabled=True,
    )
    with (
        patch("app.services.live_talk_stream.mock_llm.should_mock_llm", return_value=False),
        patch(
            "app.services.live_talk_stream.transcribe_audio",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.live_talk_stream.speech_gateway.iter_speech_to_speech_via_openrouter",
            fake_gateway,
        ),
    ):
        async for event in iter_speech_to_speech(settings, wav, filename="speech.wav"):
            if event.kind == "audio" and "yielded-clip" not in order:
                order.append("yielded-clip")

    assert order.index("yielded-clip") < order.index("rest-pcm")


@pytest.mark.asyncio
async def test_iter_speech_to_speech_rejects_unsupported_container_without_echo():
    from app.services.live_talk_stream import iter_speech_to_speech

    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 8
    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_live_talk_enabled=True,
        speech_transcription_enabled=True,
        speech_tts_enabled=True,
    )
    transcribe = AsyncMock(return_value="hello")
    with (
        patch("app.services.live_talk_stream.mock_llm.should_mock_llm", return_value=False),
        patch("app.services.live_talk_stream.transcribe_audio", transcribe),
        patch(
            "app.services.live_talk_stream.speech_gateway.iter_speech_to_speech_via_openrouter",
            AsyncMock(),
        ) as gateway,
    ):
        events = [
            event async for event in iter_speech_to_speech(settings, mp4, filename="speech.m4a")
        ]
    assert events == []
    transcribe.assert_not_called()
    gateway.assert_not_called()


def test_trim_wav_silence_shortens_quiet_file():
    from app.services.live_talk_stream import trim_wav_silence

    quiet = pcm_to_wav(b"\x00\x00" * (24000 * 8))
    trimmed = trim_wav_silence(quiet)
    assert len(trimmed) < len(quiet)
    assert trimmed[:4] == b"RIFF"


def test_trim_wav_silence_keeps_speech_island():
    from app.services.live_talk_stream import trim_wav_silence

    loud = (10_000).to_bytes(2, "little", signed=True)
    pad = b"\x00\x00" * 24000
    original = pcm_to_wav(pad + loud * 2400 + pad)
    trimmed = trim_wav_silence(original)
    assert len(trimmed) < len(original)
    assert trimmed[:4] == b"RIFF"


def test_take_live_talk_pcm_unwraps_wav_instead_of_playing_headers():
    from app.gateways.speech_gateway import take_live_talk_pcm

    pcm = (10_000).to_bytes(2, "little", signed=True) * 80
    wav = pcm_to_wav(pcm)
    stash = bytearray()
    assert take_live_talk_pcm(stash, wav[:24]) == b""
    out = take_live_talk_pcm(stash, wav[24:])
    assert out == pcm
    assert not stash


def test_take_live_talk_pcm_passes_raw_pcm16():
    from app.gateways.speech_gateway import take_live_talk_pcm

    pcm = (10_000).to_bytes(2, "little", signed=True) * 40
    stash = bytearray()
    assert take_live_talk_pcm(stash, pcm) == pcm
    assert not stash


@pytest.mark.asyncio
async def test_iter_speech_to_speech_emits_user_then_sts_audio():
    from app.services.live_talk_stream import iter_speech_to_speech

    wav = pcm_to_wav((10_000).to_bytes(2, "little", signed=True) * 16)
    order: list[str] = []

    async def transcribe(*_args: object, **_kwargs: object) -> str:
        order.append("whisper")
        return "hello"

    async def fake_gateway(*_args: object, **_kwargs: object):
        order.append("sts")
        yield (10_000).to_bytes(2, "little", signed=True) * 20_000, "Hi"

    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_live_talk_enabled=True,
        speech_transcription_enabled=True,
    )
    with (
        patch("app.services.live_talk_stream.mock_llm.should_mock_llm", return_value=False),
        patch("app.services.live_talk_stream.transcribe_audio", transcribe),
        patch(
            "app.services.live_talk_stream.speech_gateway.iter_speech_to_speech_via_openrouter",
            fake_gateway,
        ),
    ):
        events = [
            event async for event in iter_speech_to_speech(settings, wav, filename="speech.wav")
        ]
    assert order == ["whisper", "sts"]
    kinds = [event.kind for event in events]
    assert kinds.index("user") < kinds.index("audio")


@pytest.mark.asyncio
async def test_iter_speech_to_speech_still_runs_sts_when_whisper_empty():
    from app.services.live_talk_stream import iter_speech_to_speech

    wav = pcm_to_wav((10_000).to_bytes(2, "little", signed=True) * 16)

    async def fake_gateway(*_args: object, **_kwargs: object):
        yield (10_000).to_bytes(2, "little", signed=True) * 20_000, "Hi"

    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_live_talk_enabled=True,
        speech_transcription_enabled=True,
    )
    with (
        patch("app.services.live_talk_stream.mock_llm.should_mock_llm", return_value=False),
        patch(
            "app.services.live_talk_stream.transcribe_audio",
            AsyncMock(return_value=""),
        ),
        patch(
            "app.services.live_talk_stream.speech_gateway.iter_speech_to_speech_via_openrouter",
            fake_gateway,
        ),
    ):
        events = [
            event async for event in iter_speech_to_speech(settings, wav, filename="speech.wav")
        ]
    assert any(event.kind == "audio" for event in events)


@pytest.mark.asyncio
async def test_iter_speech_to_speech_continues_when_whisper_raises():
    from app.services.live_talk_stream import iter_speech_to_speech

    wav = pcm_to_wav((10_000).to_bytes(2, "little", signed=True) * 16)

    async def fake_gateway(*_args: object, **_kwargs: object):
        yield (10_000).to_bytes(2, "little", signed=True) * 20_000, "Hi"

    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_live_talk_enabled=True,
        speech_transcription_enabled=True,
    )
    with (
        patch("app.services.live_talk_stream.mock_llm.should_mock_llm", return_value=False),
        patch(
            "app.services.live_talk_stream.transcribe_audio",
            AsyncMock(side_effect=RuntimeError("whisper down")),
        ),
        patch(
            "app.services.live_talk_stream.speech_gateway.iter_speech_to_speech_via_openrouter",
            fake_gateway,
        ),
    ):
        events = [
            event async for event in iter_speech_to_speech(settings, wav, filename="speech.wav")
        ]
    assert any(event.kind == "audio" for event in events)


@pytest.mark.asyncio
async def test_speech_to_speech_falls_back_for_non_wav_input():
    from app.services.speech import speech_to_speech

    settings = Settings(
        mock_llm_enabled=False,
        openrouter_api_key="sk-or-test",
        speech_live_talk_enabled=True,
        speech_transcription_enabled=True,
        speech_tts_enabled=True,
    )
    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 8
    with (
        patch("app.services.speech.transcribe_audio", AsyncMock(return_value="hello")),
        patch(
            "app.services.speech.synthesize_speech",
            AsyncMock(return_value=(b"mp3", "audio/mpeg")),
        ),
        patch(
            "app.services.speech.speech_gateway.speech_to_speech_via_openrouter",
            AsyncMock(),
        ) as sts,
    ):
        result = await speech_to_speech(settings, mp4, filename="speech.wav")
    assert result == (b"mp3", "audio/mpeg", "hello")
    sts.assert_not_called()
