"""Live dictation: the server mints, connects and ends the composer mic's OpenAI
transcription session (``speech.dictation``), charging one voice input per take.

The recorded dictation uploaded the clip on stop, so the words came only after the
whole round trip. Now the phone streams to a transcription session; the key stays on
the server, which hangs the call up at the take's limit whatever the phone does.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.core.jobs.delayed import DELAYED_ZSET
from app.gateways.openai_speech_gateway import RealtimeCallResult, RealtimeClientSecretResult
from app.main import create_app
from app.modules.speech import dictation
from app.services.quota import counters
from app.tests.api_support import api_user

_HEADERS = {"Authorization": "Bearer tok"}
_OFFER = "v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111"
_ANSWER = "v=0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=answer"
_SETTINGS = Settings(
    openai_api_key="sk-test",
    speech_rate_limit_per_minute=0,
    speech_dictation_max_seconds=45,
)


@dataclass
class Dictation:
    """A Pro user's client over the real routes; OpenAI is recorded fakes."""

    client: TestClient
    redis: Any
    user: Any
    mint: AsyncMock
    calls: list[dict[str, Any]] = field(default_factory=list)
    hangups: list[str] = field(default_factory=list)
    call: RealtimeCallResult | None = field(
        default_factory=lambda: RealtimeCallResult(answer_sdp=_ANSWER, call_id="rtc_dict123")
    )
    hangup: str = "ended"

    def start(self, **body: Any) -> Any:
        return self.client.post("/speech/dictation/session", headers=_HEADERS, json=body)

    def session(self) -> str:
        r = self.start(language="en")
        assert r.status_code == 200, r.text
        return str(r.json()["call_id"])

    def connect(self, session: str) -> Any:
        return self.client.post(
            "/speech/dictation/connect", headers=_HEADERS, json={"call_id": session, "sdp": _OFFER}
        )

    def end(self, session: str, *, heard: bool) -> Any:
        return self.client.post(
            "/speech/dictation/end", headers=_HEADERS, json={"call_id": session, "heard": heard}
        )

    def run(self, coro: Any) -> Any:
        return asyncio.run(coro)

    def used(self) -> int:
        key = counters.daily_key("speech", self.user.id)
        return int(self.run(self.redis.get(key)) or 0)

    def scheduled(self) -> list[tuple[dict[str, Any], float]]:
        now = time.time()
        rows = self.run(self.redis.zrange(DELAYED_ZSET, 0, -1, withscores=True))
        out = []
        for member, score in rows:
            fields = json.loads(member)["fields"]
            assert fields["type"] == dictation.HANGUP_JOB
            out.append((json.loads(fields["payload"]), score - now))
        return out


def _harness(plan: str, settings: Settings) -> Iterator[Dictation]:
    user = api_user(plan=plan, locale="pt-BR")
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: settings
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    mint = AsyncMock(return_value=RealtimeClientSecretResult(value="ek_dictation", expires_at=99))
    state = Dictation(client=TestClient(app), redis=redis, user=user, mint=mint)

    async def open_call(_settings: Any, *, client_secret: str, offer_sdp: str) -> Any:
        state.calls.append({"secret": client_secret, "sdp": offer_sdp})
        return state.call

    async def hang_up(_settings: Any, call_id: str) -> str:
        state.hangups.append(call_id)
        return state.hangup

    gateway = "app.modules.speech.dictation.openai_speech_gateway"
    with (
        patch("app.modules.speech.dictation_api.get_redis_client", return_value=redis),
        patch("app.modules.speech.dictation.get_redis_client", return_value=redis),
        patch(f"{gateway}.create_transcription_client_secret", mint),
        patch(f"{gateway}.create_realtime_call", open_call),
        patch(f"{gateway}.hangup_realtime_call", hang_up),
        patch("app.modules.speech.live_call.openai_speech_gateway.hangup_realtime_call", hang_up),
    ):
        yield state


@pytest.fixture
def dic() -> Iterator[Dictation]:
    yield from _harness("pro", _SETTINGS)


# ── Mint ───────────────────────────────────────────────────────────────────


def test_a_mint_charges_one_voice_input_and_keeps_the_secret_on_the_server(dic):
    r = dic.start(language="am")

    assert r.status_code == 200
    body = r.json()
    assert "ek_dictation" not in r.text
    assert body["model"] == "gpt-live-transcribe"
    assert body["max_duration_seconds"] == 45
    assert dic.used() == 1
    kwargs = dic.mint.await_args.kwargs
    assert kwargs["language"] == "am"
    assert kwargs["model"] == "gpt-live-transcribe"
    # A hash, never the user's id.
    assert str(dic.user.id) not in kwargs["safety_identifier"]


def test_a_mint_without_a_language_uses_the_accounts_locale(dic):
    dic.start()

    assert dic.mint.await_args.kwargs["language"] == "pt-BR"


def test_the_operator_may_pick_a_gpt_4o_transcriber_but_nothing_else():
    assert dictation.dictation_model(Settings(speech_dictation_model="gpt-4o-transcribe")) == (
        "gpt-4o-transcribe"
    )
    assert dictation.dictation_model(Settings(speech_dictation_model="whisper-1")) == (
        "gpt-live-transcribe"
    )


def test_a_mint_that_fails_gives_the_voice_input_back(dic):
    dic.mint.return_value = None

    r = dic.start()

    assert r.status_code == 502
    assert dic.used() == 0


def test_free_has_no_voice_input_and_opens_the_plans():
    for state in _harness("free", _SETTINGS):
        r = state.start()
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "not_in_plan"
        state.mint.assert_not_awaited()


@pytest.mark.parametrize(
    "settings, status, code",
    [
        (Settings(openai_api_key="", speech_rate_limit_per_minute=0), 503, "not_configured"),
        (
            Settings(openai_api_key="sk", speech_live_dictation_enabled=False),
            404,
            "not_available",
        ),
        (Settings(openai_api_key="sk", speech_transcription_enabled=False), 404, "not_available"),
    ],
)
def test_a_server_without_live_dictation_sends_the_phone_to_the_recorded_path(
    settings, status, code
):
    for state in _harness("pro", settings):
        r = state.start()
        assert r.status_code == status
        assert r.json()["detail"]["code"] == code
        assert state.used() == 0


def test_the_days_cap_refuses_a_mint(dic):
    key = counters.daily_key("speech", dic.user.id)
    cap = counters.limit("speech_transcription", dic.user, _SETTINGS)
    dic.run(dic.redis.set(key, cap))

    r = dic.start()

    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "daily_limit"
    dic.mint.assert_not_awaited()


# ── Connect ────────────────────────────────────────────────────────────────


def test_connect_opens_the_call_and_schedules_its_hang_up_at_the_takes_limit(dic):
    session = dic.session()

    r = dic.connect(session)

    assert r.status_code == 200
    assert r.json() == {"sdp": _ANSWER}
    assert dic.calls == [{"secret": "ek_dictation", "sdp": _OFFER}]
    [(payload, delay)] = dic.scheduled()
    assert payload == {"user_id": str(dic.user.id), "session_id": session}
    # The take's 45 s from the phone's channel opening, plus the connect and the stop's tail.
    assert 45 + 10 <= delay <= 61
    # Once per session: the secret was taken as it was used.
    again = dic.connect(session)
    assert again.status_code == 403
    assert again.json()["detail"]["code"] == "dictation_session_ended"
    assert len(dic.calls) == 1


def test_connect_refuses_a_session_this_user_was_not_minted(dic):
    dic.session()

    r = dic.connect("someone-elses-session")

    assert r.status_code == 403
    assert dic.calls == []


def test_a_connect_that_opens_no_call_gives_the_voice_input_back(dic):
    """The phone records the clip instead, and that upload takes its own slot."""
    dic.call = None
    session = dic.session()

    r = dic.connect(session)

    assert r.status_code == 502
    assert dic.used() == 0
    assert dic.scheduled() == []


def test_a_connect_with_an_unusable_answer_hangs_up_and_gives_the_input_back(dic):
    dic.call = RealtimeCallResult(answer_sdp="not sdp", call_id="rtc_bad")
    session = dic.session()

    r = dic.connect(session)

    assert r.status_code == 502
    assert dic.hangups == ["rtc_bad"]
    assert dic.used() == 0


def test_a_connect_whose_hang_up_cannot_be_scheduled_ends_the_call(dic):
    session = dic.session()

    with patch(
        "app.modules.speech.dictation.jobs.schedule_job",
        AsyncMock(side_effect=ConnectionError("redis down")),
    ):
        r = dic.connect(session)

    assert r.status_code == 503
    assert dic.hangups == ["rtc_dict123"]
    # No take ran: the voice input goes back.
    assert dic.used() == 0


def test_a_stop_while_openai_opens_the_call_hangs_the_new_call_up(dic):
    """A tap during "Starting…": the phone's end ran before the call existed."""
    session = dic.session()
    real_open = dic.call

    async def open_call(_settings: Any, *, client_secret: str, offer_sdp: str) -> Any:
        await dictation.end(dic.redis, _SETTINGS, dic.user.id, session, heard=False)
        return real_open

    with patch(
        "app.modules.speech.dictation.openai_speech_gateway.create_realtime_call", open_call
    ):
        r = dic.connect(session)

    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "dictation_session_ended"
    assert dic.hangups == ["rtc_dict123"]
    assert dic.used() == 0


# ── End ────────────────────────────────────────────────────────────────────


def test_a_take_that_heard_words_hangs_up_and_keeps_its_charge(dic):
    session = dic.session()
    dic.connect(session)

    r = dic.end(session, heard=True)

    assert r.status_code == 204
    assert dic.hangups == ["rtc_dict123"]
    assert dic.used() == 1
    # Idempotent: the call is forgotten once it is over.
    dic.end(session, heard=True)
    assert dic.hangups == ["rtc_dict123"]


def test_a_take_that_heard_nothing_gives_the_voice_input_back_once(dic):
    session = dic.session()
    dic.connect(session)

    dic.end(session, heard=False)
    dic.end(session, heard=False)

    assert dic.used() == 0
    assert dic.hangups == ["rtc_dict123"]


def test_the_phones_word_that_nothing_was_heard_refunds_only_so_often_a_day(dic):
    for _ in range(dictation.EMPTY_REFUNDS_PER_DAY + 3):
        session = dic.session()
        dic.connect(session)
        dic.end(session, heard=False)

    assert dic.used() == 3


def test_a_take_whose_call_never_opened_is_refunded_without_the_cap(dic):
    """A stop during "Starting…" heard nothing for certain: it never uses a capped refund."""
    for _ in range(dictation.EMPTY_REFUNDS_PER_DAY + 3):
        session = dic.session()
        dic.end(session, heard=False)

    assert dic.used() == 0
    # The cap is still whole for the takes that did open a call.
    session = dic.session()
    dic.connect(session)
    dic.end(session, heard=False)
    assert dic.used() == 0


def test_a_take_is_charged_at_live_dictations_own_price(dic):
    session = dic.session()

    with patch(
        "app.modules.speech.dictation.quota_service.record_voice_spend", AsyncMock()
    ) as spend:
        dic.connect(session)

    spend.assert_awaited_once()
    assert spend.await_args.args[1] == pytest.approx(0.017)


def test_another_user_can_neither_connect_nor_end_a_take(dic):
    """The secret, call and slot keys are per user: B holding A's real call_id gets nothing."""
    session = dic.session()
    other = api_user(plan="pro")
    dic.client.app.dependency_overrides[get_current_user] = lambda: other

    connect = dic.connect(session)
    end = dic.end(session, heard=False)

    assert connect.status_code == 403
    assert connect.json()["detail"]["code"] == "dictation_session_ended"
    assert end.status_code == 204
    assert dic.calls == []
    # A's slot is still charged, and A's take still connects.
    assert dic.used() == 1
    dic.client.app.dependency_overrides[get_current_user] = lambda: dic.user
    assert dic.connect(session).status_code == 200


def test_an_unconfirmed_hang_up_is_left_to_a_job_that_runs_now(dic):
    dic.hangup = "failed"
    session = dic.session()
    dic.connect(session)

    dic.end(session, heard=True)

    delays = sorted(delay for _payload, delay in dic.scheduled())
    assert delays[0] <= 1 and delays[1] >= 45


def test_an_end_before_the_connect_opens_nothing(dic):
    session = dic.session()
    dic.end(session, heard=False)

    assert dic.connect(session).status_code == 403
    assert dic.calls == []
    assert dic.used() == 0


# ── The hang-up job ────────────────────────────────────────────────────────


def _job(dic: Dictation, session: str) -> None:
    payload = {"user_id": str(dic.user.id), "session_id": session}
    dic.run(dictation.handle_hangup_job(_SETTINGS, payload))


def test_the_job_ends_a_take_the_phone_never_stopped(dic):
    session = dic.session()
    dic.connect(session)

    _job(dic, session)

    assert dic.hangups == ["rtc_dict123"]
    assert dic.used() == 1


def test_the_job_raises_while_the_hang_up_is_unconfirmed(dic):
    dic.hangup = "failed"
    session = dic.session()
    dic.connect(session)

    with pytest.raises(dictation.DictationUnconfirmedError):
        _job(dic, session)


@pytest.mark.parametrize(
    "payload", [{}, {"user_id": "nope", "session_id": "s"}, {"user_id": str(uuid4())}]
)
def test_the_job_ignores_a_payload_it_cannot_read(dic, payload):
    dic.run(dictation.handle_hangup_job(_SETTINGS, payload))
    assert dic.hangups == []


def test_the_job_is_registered():
    from app.background import handlers
    from app.core.jobs import queue

    handlers.register_all()
    assert queue._HANDLERS[dictation.HANGUP_JOB] is dictation.handle_hangup_job
