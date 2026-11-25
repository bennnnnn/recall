"""Listen (a reply played aloud) by the text's language: Kokoro on OpenRouter for English,
Spanish, French, Hindi and Portuguese, tts-1 for the rest and for a text whose language is
unclear, tts-1 again when Kokoro fails; and the reply voice the user picked is the one heard.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.models import model_catalog
from app.models.schemas.auth import UserOut, UserUpdate
from app.models.voice_catalog import picker_voices, voice_for
from app.modules.speech.service import ListenClip, synthesize_speech
from app.modules.speech.text_language import _WORDS, UNSURE, clip_language, text_language
from app.tests.api_support import api_user, app_with_user

FIXTURE = Path(__file__).resolve().parents[6] / "docs" / "fixtures" / "reply_voices.json"
_OPENROUTER = "app.gateways.openrouter_speech_gateway.get_pooled_client"
_OPENAI = "app.gateways.speech_gateway.get_pooled_client"

SPANISH = "Claro, aquí tienes la respuesta: el agua hierve a cien grados y es muy fácil de medir."
FRENCH = "Bien sûr, voici la réponse : l'eau bout à cent degrés et c'est très facile à mesurer."
PORTUGUESE = "Claro, aqui está a resposta: a água ferve a cem graus e isso é muito fácil de medir."
ENGLISH = "Sure, here is the answer: water boils at one hundred degrees and it is easy to measure."
HINDI = "ज़रूर, यह रहा जवाब: पानी सौ डिग्री पर उबलता है और इसे मापना आसान है।"
RUSSIAN = "Конечно, вот ответ: вода кипит при ста градусах, и это легко измерить."
AMHARIC = "እርግጥ ነው፣ መልሱ ይህ ነው፦ ውሃ በመቶ ዲግሪ ይፈላል።"
TURKISH = "Tabii, işte cevap: su yüz derecede kaynar ve bunu ölçmek çok kolaydır."
ITALIAN = (
    "Certo, ecco la risposta: l'acqua bolle a cento gradi ed è molto facile da misurare per tutti."
)
GERMAN = "Natürlich, hier ist die Antwort: Wasser kocht bei hundert Grad und das ist nicht schwer."


@pytest.mark.parametrize(
    "text, language",
    [
        (ENGLISH, "en"),
        ("Hello! How can I help you today?", "en"),
        (SPANISH, "es"),
        ("¿Qué tal? Hoy está muy bien el día.", "es"),
        (FRENCH, "fr"),
        (PORTUGUESE, "pt"),
        ("Você pode me dizer onde fica a estação? Não sei o caminho.", "pt"),
        # Words two languages write are in no list (review, 2026-11-24): "mais" (fr, pt),
        # "dos" (es, pt), "il y a" (French, not Spanish "y").
        ("Você pode usar mais água.", "pt"),
        ("Hay dos soluciones: x = 2 y x = 3.", "es"),
        ("Il y a deux solutions et elles sont simples.", "fr"),
        (HINDI, "hi"),
        (RUSSIAN, "ru"),
        (AMHARIC, "am"),
        (TURKISH, "tr"),
        # No clear language: tts-1 reads these.
        ("Hello", None),
        ("x = 3.5, y = 4", None),
        ("", None),
        ("The word for water in Russian is вода, said vah-DAH.", None),
        ("Python और API दोनों सीखने के लिए अच्छे हैं, Python से शुरू करें।", None),
    ],
)
def test_text_language_names_only_a_plain_language(text: str, language: str | None) -> None:
    assert text_language(text) == language


def test_no_word_is_in_two_languages_lists() -> None:
    seen: dict[str, str] = {}
    shared = []
    for language, words in _WORDS.items():
        shared += [(word, seen[word], language) for word in words if word in seen]
        seen.update(dict.fromkeys(words, language))
    assert shared == []


@pytest.mark.parametrize("text", [ITALIAN, GERMAN])
def test_a_language_kokoro_reads_but_the_app_has_not_is_never_read_as_one_it_has(
    text: str,
) -> None:
    # Italian and German are listed only so that they are never Spanish, French or
    # Portuguese: Kokoro's voice of one of those would mispronounce every word.
    assert text_language(text) not in {"en", "es", "fr", "pt", "hi"}


@pytest.mark.parametrize(
    "clip, lead, language",
    [
        # A clip of numbers or a name follows its reply's language.
        ("1, 2, 3 y 4.", "es", "es"),
        ("Paris, 2.1 million (2023).", "en", "en"),
        # Letters written as symbols are no other script (review, 2026-11-24).
        ("R = 10 Ω, so I = 1.2 A.", "en", "en"),
        ("θ = 30°", "en", "en"),
        ("A cell is about 10 µm across.", "en", "en"),
        ("el 1º de mayo", "es", "es"),
        # A clip that reads as another language, or holds another script, goes to tts-1.
        (ENGLISH, "es", None),
        ("Moscú se escribe Москва.", "es", None),
        # A lead no language was read for keeps the whole reply on tts-1.
        (ENGLISH, UNSURE, None),
        # No record of the lead: the clip decides alone.
        (SPANISH, None, "es"),
    ],
)
def test_clip_language_follows_the_reply_unless_the_clip_says_otherwise(
    clip: str, lead: str | None, language: str | None
) -> None:
    assert clip_language(clip, lead) == language


def test_kokoro_reads_its_five_app_languages_and_tts1_the_rest() -> None:
    for language in ("en", "es", "fr", "hi", "pt"):
        assert model_catalog.read_aloud_aliases(language) == (
            "speech-tts-kokoro-model",
            "speech-tts-model",
        )
    unclear: tuple[str | None, ...] = ("ru", "tr", "am", None)
    for other in unclear:
        assert model_catalog.read_aloud_aliases(other) == ("speech-tts-model",)
    kokoro = model_catalog.get("speech-tts-kokoro-model")
    assert (kokoro.provider, kokoro.api_key_field) == ("openrouter", "openrouter_api_key")
    assert model_catalog.openrouter_slug("speech-tts-kokoro-model") == "hexgrad/kokoro-82m"


def _fixture() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text())
    return data


@pytest.mark.parametrize("language", ["en", "es", "fr", "hi", "pt", "ru", "tr", "am"])
def test_the_reply_voice_picker_matches_the_shared_fixture(language: str) -> None:
    data = _fixture()
    listed = data["languages"][language]
    expected = data["openai"] if listed == "openai" else listed
    assert [{"id": v.id, "female": v.female} for v in picker_voices(language)] == expected


def test_reply_voice_defaults_and_swaps_match_the_shared_fixture() -> None:
    for case in _fixture()["defaults"]:
        alias = model_catalog.read_aloud_aliases(case["language"])[0]
        heard = voice_for(alias, case["language"], case["reply_voice"], case["live_voice"])
        assert heard == case["plays"], case


def test_a_picked_reply_voice_is_the_one_heard_and_tts1_has_no_live_only_voice() -> None:
    kokoro, openai = "speech-tts-kokoro-model", "speech-tts-model"
    assert voice_for(kokoro, "en", "bm_george", "marin") == "bm_george"
    assert voice_for(openai, "ru", "onyx", "marin") == "onyx"
    # Kokoro failed on an English clip: tts-1 reads it in a voice of the same gender.
    assert voice_for(openai, "en", "bm_george", None) == "ash"
    for live in ("marin", "cedar", "ballad", "verse"):
        assert voice_for(openai, "ru", None, live) in {v.id for v in picker_voices("ru")}


def _response(content: bytes, content_type: str, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.content = content
    response.text = "" if status < 400 else '{"error":{"message":"upstream"}}'
    response.headers = {"content-type": content_type}
    response.raise_for_status = MagicMock()
    return response


def _client(response: MagicMock) -> AsyncMock:
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    return client


def _keys(openrouter_api_key: str = "or-test") -> Settings:
    return Settings(
        openai_api_key="sk-test", openrouter_api_key=openrouter_api_key, mock_llm_enabled=False
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text, voice", [(SPANISH, "ef_dora"), (HINDI, "hf_alpha"), (FRENCH, "ff_siwis")]
)
async def test_a_kokoro_language_plays_through_openrouter_as_mp3(text: str, voice: str) -> None:
    openrouter = _client(_response(b"ID3kokoro", "audio/mpeg"))
    openai = _client(_response(b"ID3tts1", "audio/mpeg"))
    played: list[ListenClip] = []
    with patch(_OPENROUTER, return_value=openrouter), patch(_OPENAI, return_value=openai):
        result = await synthesize_speech(
            _keys(), text, reply_voice="af_bella", on_played=played.append
        )
    assert result == (b"ID3kokoro", "audio/mpeg")
    openai.post.assert_not_called()
    url = openrouter.post.call_args.args[0]
    body = openrouter.post.call_args.kwargs["json"]
    assert url == "https://openrouter.ai/api/v1/audio/speech"
    assert openrouter.post.call_args.kwargs["headers"]["Authorization"] == "Bearer or-test"
    assert body["model"] == "hexgrad/kokoro-82m"
    assert body["voice"] == voice  # af_bella's gender in the text's own language
    assert body["response_format"] == "mp3"
    assert body["provider"]["order"] == ["deepinfra"]
    (clip,) = played
    assert clip.alias == "speech-tts-kokoro-model"
    assert clip.usd == pytest.approx(len(" ".join(text.split())) * 4.0 / 1_000_000)
    assert clip.reply_language == text_language(text)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [RUSSIAN, TURKISH, AMHARIC, "Hello"])
async def test_other_languages_and_unclear_text_play_through_tts1(text: str) -> None:
    openrouter = _client(_response(b"ID3kokoro", "audio/mpeg"))
    openai = _client(_response(b"ID3tts1", "audio/mpeg"))
    played: list[ListenClip] = []
    with patch(_OPENROUTER, return_value=openrouter), patch(_OPENAI, return_value=openai):
        result = await synthesize_speech(_keys(), text, voice="cedar", on_played=played.append)
    assert result == (b"ID3tts1", "audio/mpeg")
    openrouter.post.assert_not_called()
    body = openai.post.call_args.kwargs["json"]
    assert (body["model"], body["voice"]) == ("tts-1", "ash")
    (clip,) = played
    assert clip.usd == pytest.approx(len(text) * 15.0 / 1_000_000)
    assert clip.reply_language == UNSURE  # the rest of the reply stays on tts-1


@pytest.mark.asyncio
async def test_a_rest_clip_of_numbers_plays_in_its_replys_kokoro_voice() -> None:
    openrouter = _client(_response(b"ID3kokoro", "audio/mpeg"))
    openai = _client(_response(b"ID3tts1", "audio/mpeg"))
    with patch(_OPENROUTER, return_value=openrouter), patch(_OPENAI, return_value=openai):
        result = await synthesize_speech(
            _keys(), "1, 2, 3 y 4.", reply_voice="af_heart", reply_language="es"
        )
    assert result == (b"ID3kokoro", "audio/mpeg")
    openai.post.assert_not_called()
    assert openrouter.post.call_args.kwargs["json"]["voice"] == "ef_dora"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kokoro",
    [
        _response(b"", "application/json", status=502),
        _response(b"", "audio/mpeg"),
        _response(b'{"error":1}', "application/json"),
    ],
)
async def test_a_kokoro_failure_falls_back_to_tts1(kokoro: MagicMock) -> None:
    openrouter = _client(kokoro)
    openai = _client(_response(b"ID3tts1", "audio/mpeg"))
    calls: list[str] = []
    played: list[ListenClip] = []
    with patch(_OPENROUTER, return_value=openrouter), patch(_OPENAI, return_value=openai):
        result = await synthesize_speech(
            _keys(),
            ENGLISH,
            reply_voice="am_michael",
            on_call=lambda: calls.append("call"),
            on_played=played.append,
        )
    assert result == (b"ID3tts1", "audio/mpeg")
    assert openai.post.call_args.kwargs["json"]["voice"] == "ash"
    assert calls == ["call"]
    # tts-1 played it: the reply's rest clips stay on tts-1, in the same voice.
    assert [(clip.alias, clip.reply_language) for clip in played] == [("speech-tts-model", UNSURE)]


@pytest.mark.asyncio
async def test_a_kokoro_timeout_falls_back_to_tts1() -> None:
    openrouter = AsyncMock()
    openrouter.post = AsyncMock(side_effect=TimeoutError())
    openai = _client(_response(b"ID3tts1", "audio/mpeg"))
    with patch(_OPENROUTER, return_value=openrouter), patch(_OPENAI, return_value=openai):
        assert await synthesize_speech(_keys(), ENGLISH) == (b"ID3tts1", "audio/mpeg")


@pytest.mark.asyncio
async def test_without_an_openrouter_key_kokoro_languages_play_through_tts1() -> None:
    openrouter = _client(_response(b"ID3kokoro", "audio/mpeg"))
    openai = _client(_response(b"ID3tts1", "audio/mpeg"))
    settings = _keys(openrouter_api_key="")
    with patch(_OPENROUTER, return_value=openrouter), patch(_OPENAI, return_value=openai):
        assert await synthesize_speech(settings, SPANISH) == (b"ID3tts1", "audio/mpeg")
    openrouter.post.assert_not_called()


@pytest.mark.asyncio
async def test_without_any_key_kokoro_languages_get_no_audio() -> None:
    settings = Settings(openai_api_key="", openrouter_api_key="", mock_llm_enabled=False)
    with patch(_OPENROUTER) as openrouter, patch(_OPENAI) as openai:
        assert await synthesize_speech(settings, SPANISH) is None
    openrouter.assert_not_called()
    openai.assert_not_called()


def _post_tts(client: TestClient, text: str, **extra: str) -> Any:
    return client.post(
        "/speech/tts", headers={"Authorization": "Bearer tok"}, json={"text": text, **extra}
    )


def test_a_reply_keeps_its_leads_language_and_every_clip_is_paid_for() -> None:
    user = api_user(plan="pro", reply_voice="em_alex")
    client = TestClient(app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    calls: list[dict[str, Any]] = []

    async def synth(_settings: Any, text: str, **kwargs: Any) -> tuple[bytes, str]:
        calls.append(kwargs)
        kwargs["on_played"](ListenClip("speech-tts-kokoro-model", "es", len(text) * 4e-6))
        return b"mp3", "audio/mpeg"

    spend = AsyncMock()
    with (
        patch("app.modules.speech.api.get_redis_client", return_value=fake_redis),
        patch("app.modules.speech.api.speech_service.synthesize_speech", synth),
        patch("app.modules.speech.api.quota_service.record_voice_spend", spend),
    ):
        lead = _post_tts(client, SPANISH, part="lead")
        lead_hash = lead.json()["lead_hash"]
        rest = _post_tts(client, "1, 2, 3 y 4.", part="rest", lead_hash=lead_hash)
    assert lead.status_code == rest.status_code == 200
    assert base64.b64decode(rest.json()["audio_base64"]) == b"mp3"
    first, second = calls
    assert first["reply_language"] is None
    assert second["reply_language"] == "es"
    assert second["reply_voice"] == "em_alex"
    # The rest clip took no daily slot, and its characters are still paid for.
    assert [call.args[1] for call in spend.await_args_list] == [
        pytest.approx(len(SPANISH) * 4e-6),
        pytest.approx(len("1, 2, 3 y 4.") * 4e-6),
    ]


def test_a_lead_tts1_played_keeps_the_rest_of_the_reply_on_tts1() -> None:
    client = TestClient(app_with_user(api_user(plan="pro")))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    calls: list[dict[str, Any]] = []

    async def synth(_settings: Any, _text: str, **kwargs: Any) -> tuple[bytes, str]:
        calls.append(kwargs)
        # Kokoro failed on the English lead: tts-1 played it.
        kwargs["on_played"](ListenClip("speech-tts-model", "en", 0.001))
        return b"mp3", "audio/mpeg"

    with (
        patch("app.modules.speech.api.get_redis_client", return_value=fake_redis),
        patch("app.modules.speech.api.speech_service.synthesize_speech", synth),
        patch("app.modules.speech.api.quota_service.record_voice_spend", AsyncMock()),
    ):
        lead_hash = _post_tts(client, ENGLISH, part="lead").json()["lead_hash"]
        _post_tts(client, "And that is all.", part="rest", lead_hash=lead_hash)
    assert calls[1]["reply_language"] == UNSURE


def test_the_spend_recorded_is_what_the_service_reports() -> None:
    user = api_user(plan="pro")
    client = TestClient(app_with_user(user))
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def synth(*_args: Any, on_played: Any = None, **_kwargs: Any) -> tuple[bytes, str]:
        on_played(ListenClip("speech-tts-model", None, 0.0006))
        return b"mp3", "audio/mpeg"

    spend = AsyncMock()
    with (
        patch("app.modules.speech.api.get_redis_client", return_value=fake_redis),
        patch("app.modules.speech.api.speech_service.synthesize_speech", synth),
        patch("app.modules.speech.api.quota_service.record_voice_spend", spend),
    ):
        assert _post_tts(client, ENGLISH).status_code == 200
    spend.assert_awaited_once_with(fake_redis, pytest.approx(0.0006))


@pytest.mark.parametrize(
    "locale, picked, live, heard",
    [
        ("en", None, "cedar", "am_michael"),
        ("ru", None, "marin", "coral"),
        ("es", "af_heart", None, "ef_dora"),
        ("en", "af_heart", "cedar", "af_heart"),
    ],
)
def test_the_account_sends_the_pick_and_the_voice_heard(
    locale: str, picked: str | None, live: str | None, heard: str
) -> None:
    """The phone ticks the pick (null: follow live talk) and names the voice heard."""
    out = UserOut.model_validate(api_user(locale=locale, reply_voice=picked, tts_voice=live))
    body = out.model_dump()
    assert (body["reply_voice"], body["reply_voice_heard"]) == (picked, heard)


def test_only_a_voice_a_reply_model_has_can_be_saved() -> None:
    assert UserUpdate(reply_voice="hm_psi").reply_voice == "hm_psi"
    assert UserUpdate(reply_voice=None).reply_voice is None
    for wrong in ("marin", "af_alloy", "Kore", ""):
        with pytest.raises(ValueError):
            UserUpdate(reply_voice=wrong)
