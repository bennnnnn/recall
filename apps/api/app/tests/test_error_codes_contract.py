"""The refusals a client switches on, as the API sends them (code-health audit DUP-10).

The phone recovered a refusal's meaning by matching the server's English ("Too many
scans in a row…", ``/content type/``), so a reworded message silently changed what it
did. Each refusal now names a ``code``. ``docs/fixtures/error_codes.json`` is written
here from real requests (``UPDATE_ERROR_CODES=1``) and read by the phone's tests, which
key their words and actions on the codes.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_settings_dep
from app.main import create_app
from app.models.orm import User
from app.models.schemas.scan import SCAN_MAX_IMAGE_BYTES
from app.modules.account.email_authority import AccountExistsError
from app.services.quota import counters

FIXTURE = Path(__file__).resolve().parents[4] / "docs" / "fixtures" / "error_codes.json"
_AUTH = {"Authorization": "Bearer tok"}
_IMAGE = base64.b64encode(b"\xff\xd8\xff fake jpeg").decode()


def _client(user: Any, settings: Settings | None = None) -> TestClient:
    async def db() -> Any:
        yield SimpleNamespace(refresh=AsyncMock(), commit=AsyncMock())

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_settings_dep] = lambda: settings or Settings()
    return TestClient(app)


def _user(*, consented: bool = True) -> Any:
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.plan = "free"
    user.ai_data_consent_at = object() if consented else None
    return user


def _refusal(response: Any) -> dict[str, Any]:
    return {"status": response.status_code, "detail": response.json()["detail"]}


def _scan(body: dict[str, Any], *, settings: Settings | None = None, **redis: bool) -> Any:
    with (
        patch("app.services.scan_read.get_redis_client", return_value=MagicMock()),
        patch(
            "app.services.scan_read.quota_service.global_spend_exceeded",
            AsyncMock(return_value=redis.get("spend_exceeded", False)),
        ),
        patch("app.services.scan_read.quota_service.record_global_spend", AsyncMock()),
        patch(
            "app.services.scan_read.allow_request_fail_closed",
            AsyncMock(return_value=redis.get("allowed", True)),
        ),
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
    ):
        return _client(_user(), settings).post("/math/scan/read", headers=_AUTH, json=body)


async def _seed(redis: Any, key: str, value: int) -> None:
    await redis.set(key, value, ex=60)


def _presign(content_type: str, size_bytes: int, *, at_daily_cap: bool = False) -> Any:
    user = _user()
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    if at_daily_cap:
        day = counters.utc_today().isoformat()
        cap = counters.limit("image_upload", user, Settings())
        asyncio.run(_seed(fake_redis, f"imgup:{user.id}:{day}", cap))
    with (
        patch("app.modules.attachments.upload.get_redis_client", return_value=fake_redis),
    ):
        return _client(user).post(
            "/attachments/presign",
            headers=_AUTH,
            json={"content_type": content_type, "size_bytes": size_bytes},
        )


def _transcribe(*, at_daily_cap: bool = False, allowed: bool = True) -> Any:
    """POST /speech/transcribe for a Pro user, at the day's cap or past the minute's rate."""
    user = _user()
    user.plan = "pro"
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    if at_daily_cap:
        cap = counters.limit("speech_transcription", user, Settings())
        key = counters.daily_key("speech", user.id, counters.utc_today())
        asyncio.run(_seed(fake_redis, key, cap))
    with (
        patch("app.modules.speech.api.get_redis_client", return_value=fake_redis),
        patch(
            "app.modules.speech.gates.allow_request_fail_closed",
            AsyncMock(return_value=allowed),
        ),
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
    ):
        return _client(user).post(
            "/speech/transcribe",
            headers=_AUTH,
            json={"audio_base64": base64.b64encode(b"audio").decode(), "filename": "a.m4a"},
        )


def _generate(code: str) -> Any:
    """POST /images/generate refused the way the picture service refuses."""
    from app.modules.images.generation import ImageGenerationError

    refusals = {
        "daily_limit": ImageGenerationError(
            "No more pictures today.",
            status_code=429,
            code="daily_limit",
            feature="image_generation",
        ),
        "content_blocked": ImageGenerationError(
            "That picture can't be made.",
            status_code=422,
            code="content_blocked",
            feature="image_generation",
        ),
    }
    with (
        patch(
            "app.modules.images.api.image_generation_service.generate_for_chat",
            AsyncMock(side_effect=refusals[code]),
        ),
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
    ):
        return _client(_user()).post(
            "/images/generate", headers=_AUTH, json={"chat_id": str(uuid4()), "prompt": "a cat"}
        )


def _bodies() -> dict[str, dict[str, Any]]:
    too_big = base64.b64encode(b"\xff" * (SCAN_MAX_IMAGE_BYTES + 1)).decode()
    with (
        patch("app.core.rest_rate_limit.allow_request", AsyncMock(return_value=True)),
    ):
        consent = _client(_user(consented=False)).post(
            "/math/scan/read", headers=_AUTH, json={"image_base64": _IMAGE}
        )
    with (
        patch(
            "app.modules.account.api.auth_service.login_with_google",
            AsyncMock(side_effect=AccountExistsError("apple")),
        ),
        patch("app.modules.account.api._enforce_login_rate_limit", AsyncMock()),
    ):
        exists = _client(_user()).post("/auth/google", json={"id_token": "token"})
    return {
        "consent_required": _refusal(consent),
        "account_exists": _refusal(exists),
        "scan_not_available": _refusal(
            _scan({"image_base64": _IMAGE}, settings=Settings(math_tools_enabled=False))
        ),
        "scan_too_large": _refusal(_scan({"image_base64": too_big})),
        "scan_invalid_image": _refusal(_scan({"image_base64": "not base64!"})),
        "scan_rate_limited": _refusal(_scan({"image_base64": _IMAGE}, allowed=False)),
        "scan_spend_cap": _refusal(_scan({"image_base64": _IMAGE}, spend_exceeded=True)),
        "presign_unsupported_type": _refusal(_presign("application/x-msdownload", 100)),
        # The schema caps the size: FastAPI's own 422, which the phone reads as too large.
        "presign_too_large": {
            "status": (too_large := _presign("image/png", 10_485_761)).status_code,
            "detail": too_large.json()["detail"],
        },
        "presign_daily_limit": _refusal(_presign("image/png", 128, at_daily_cap=True)),
        "dictation_daily_limit": _refusal(_transcribe(at_daily_cap=True)),
        "dictation_rate_limited": _refusal(_transcribe(allowed=False)),
        "image_daily_limit": _refusal(_generate("daily_limit")),
        "image_content_blocked": _refusal(_generate("content_blocked")),
    }


@pytest.mark.usefixtures("consent_enforced")
def test_the_fixture_is_what_the_api_sends() -> None:
    bodies = _bodies()
    if os.environ.get("UPDATE_ERROR_CODES"):
        FIXTURE.write_text(json.dumps(bodies, indent=1, ensure_ascii=False) + "\n")
    assert json.loads(FIXTURE.read_text()) == bodies


def test_every_refusal_in_the_fixture_names_a_code() -> None:
    for name, refusal in json.loads(FIXTURE.read_text()).items():
        assert refusal["status"] >= 400, name
        if refusal["status"] != 422:  # FastAPI's validation body: a list of errors
            assert refusal["detail"]["code"] and refusal["detail"]["message"], name
