"""Image generation router tests."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.deps import get_settings_dep
from app.gateways.storage_gateway import LocalStorageGateway, PresignedUpload
from app.main import create_app
from app.models.orm import Chat, Message, User


def _fake_user(*, plan: str = "pro") -> User:
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "test@recall.local"
    user.plan = plan
    return user


def _app_with_user(user: User, *, settings: Settings | None = None):
    from app.core.deps import get_current_user

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_settings_dep] = lambda: settings or Settings()
    return app


def test_generate_image_requires_pro():
    user = _fake_user(plan="free")
    client = TestClient(_app_with_user(user))
    r = client.post(
        "/images/generate",
        headers={"Authorization": "Bearer tok"},
        json={"chat_id": str(uuid4()), "prompt": "a cat"},
    )
    assert r.status_code == 403


def test_generate_image_quota_exhausted():
    user = _fake_user(plan="pro")
    app = _app_with_user(user, settings=Settings(daily_image_generations_pro=1))
    fake_redis = AsyncMock()
    fake_redis.incrby = AsyncMock(return_value=2)
    fake_redis.expire = AsyncMock()

    with (
        patch("app.services.image_generation.get_redis_client", return_value=fake_redis),
        patch(
            "app.services.image_generation.chats_repo.get_by_id",
            AsyncMock(return_value=MagicMock()),
        ),
    ):
        client = TestClient(app)
        r = client.post(
            "/images/generate",
            headers={"Authorization": "Bearer tok"},
            json={"chat_id": str(uuid4()), "prompt": "a cat"},
        )
    assert r.status_code == 429


def test_generate_image_rejects_oversized_result():
    """BUG FIX: last-line-of-defense size check, matching the
    presign + actual-bytes double-check every normal attachment upload gets."""
    from app.services.attachment_content import MAX_ATTACHMENT_SIZE

    user = _fake_user(plan="pro")
    chat_id = uuid4()
    app = _app_with_user(user)

    chat = MagicMock(spec=Chat)
    chat.id = chat_id

    fake_redis = AsyncMock()
    fake_redis.incrby = AsyncMock(return_value=1)
    fake_redis.expire = AsyncMock()

    oversized = b"\x89PNG\r\n\x1a\n" + b"0" * MAX_ATTACHMENT_SIZE

    with (
        patch("app.services.image_generation.get_redis_client", return_value=fake_redis),
        patch(
            "app.services.image_generation.chats_repo.get_by_id",
            AsyncMock(return_value=chat),
        ),
        patch(
            "app.services.image_generation.generate_image",
            AsyncMock(return_value=(oversized, "image/png")),
        ),
    ):
        client = TestClient(app)
        r = client.post(
            "/images/generate",
            headers={"Authorization": "Bearer tok"},
            json={"chat_id": str(chat_id), "prompt": "a cat"},
        )

    assert r.status_code == 502
    # Reserved once (+1) on entry, refunded once (-1) after the size check rejects it.
    assert fake_redis.incrby.await_count == 2
    assert fake_redis.incrby.await_args_list[1].args[1] == -1


def test_generate_image_success():
    user = _fake_user(plan="pro")
    chat_id = uuid4()
    attachment_id = uuid4()
    app = _app_with_user(user)

    chat = MagicMock(spec=Chat)
    chat.id = chat_id

    user_msg = MagicMock(spec=Message)
    user_msg.id = uuid4()
    user_msg.role = "user"
    user_msg.content = "Generate image: a cat"
    user_msg.model = None
    user_msg.feedback = None
    user_msg.created_at = datetime.now()

    assistant_msg = MagicMock(spec=Message)
    assistant_msg.id = uuid4()
    assistant_msg.role = "assistant"
    assistant_msg.content = f"[Image: /attachments/{attachment_id}/file]"
    assistant_msg.model = "image-gen-model"
    assistant_msg.feedback = None
    assistant_msg.created_at = datetime.now()

    gateway = MagicMock(spec=LocalStorageGateway)
    gateway.presign_upload = AsyncMock(
        return_value=PresignedUpload(
            attachment_id=str(attachment_id),
            upload_url=f"/attachments/{attachment_id}/upload",
            storage_key=f"{user.id}/{attachment_id}",
            headers={"Content-Type": "image/png"},
            api_upload=True,
        )
    )
    gateway.write_bytes = AsyncMock()

    fake_redis = AsyncMock()
    fake_redis.incrby = AsyncMock(return_value=1)
    fake_redis.expire = AsyncMock()

    fake_session = AsyncMock()

    async def _get_db():
        yield fake_session

    from app.core.db import get_db

    app.dependency_overrides[get_db] = _get_db

    with (
        patch("app.services.image_generation.get_redis_client", return_value=fake_redis),
        patch(
            "app.services.image_generation.chats_repo.get_by_id",
            AsyncMock(return_value=chat),
        ),
        patch(
            "app.services.image_generation.generate_image",
            AsyncMock(return_value=(b"\x89PNG\r\n", "image/png")),
        ),
        patch("app.services.image_generation.get_storage_gateway", return_value=gateway),
        patch("app.services.image_generation.attachments_repo.create_pending", AsyncMock()),
        patch(
            "app.services.image_generation.messages_repo.create",
            AsyncMock(side_effect=[user_msg, assistant_msg]),
        ),
        patch(
            "app.services.image_generation.attachments_repo.link_to_message",
            AsyncMock(return_value=1),
        ),
        patch("app.services.image_generation.bytes_match_claimed", return_value=True),
    ):
        client = TestClient(app)
        r = client.post(
            "/images/generate",
            headers={"Authorization": "Bearer tok"},
            json={"chat_id": str(chat_id), "prompt": "a cat"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["role"] == "assistant"
    assert "/attachments/" in body["assistant_message"]["content"]
    gateway.write_bytes.assert_awaited_once()
