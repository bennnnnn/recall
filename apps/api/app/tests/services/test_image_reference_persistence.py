from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.image_generation import ImageGenerationError, generate_for_chat


@pytest.mark.asyncio
@pytest.mark.parametrize("regenerate,fail_link", [(False, False), (False, True), (True, False)])
async def test_image_reference_persistence_is_atomic_and_regeneration_reuses_input(
    regenerate, fail_link
):
    user = SimpleNamespace(id=uuid4())
    reference_id, output_id, chat_id = uuid4(), uuid4(), uuid4()
    source = SimpleNamespace(id=reference_id, content_type="image/png")
    prior = SimpleNamespace(
        id=uuid4(), content=f"Make it blue\n[Image: /attachments/{reference_id}/file]"
    )
    assistant = SimpleNamespace(id=uuid4())
    session = AsyncMock()
    session.__aenter__.return_value = session
    gateway = AsyncMock()
    gateway.presign_upload.return_value = SimpleNamespace(
        attachment_id=str(output_id), storage_key="generated-output"
    )
    generated = AsyncMock(return_value=(b"png", "image/png"))
    load = AsyncMock(return_value=[(source, b"reference-bytes")])
    create = AsyncMock(side_effect=[assistant] if regenerate else [prior, assistant])
    link = AsyncMock(return_value=0 if fail_link else 1)
    refund = AsyncMock()
    with (
        patch("app.services.image_generation.SessionLocal", return_value=session),
        patch("app.services.image_generation.plan_service.is_pro", return_value=True),
        patch(
            "app.services.image_generation.chats_repo.get_by_id", AsyncMock(return_value=object())
        ),
        patch(
            "app.services.image_generation.messages_repo.get_last_user",
            AsyncMock(return_value=prior),
        ),
        patch("app.services.image_generation.get_storage_gateway", return_value=gateway),
        patch("app.services.image_generation.get_redis_client", return_value=AsyncMock()),
        patch("app.services.image_generation.load_reference_images", load),
        patch(
            "app.services.image_generation.quota_service.image_generation_limit_for_user",
            return_value=10,
        ),
        patch(
            "app.services.image_generation.quota_service.reserve_image_generation",
            AsyncMock(return_value=True),
        ),
        patch("app.services.image_generation.quota_service.refund_image_generation", refund),
        patch("app.services.image_generation.generate_image", generated),
        patch("app.services.image_generation.bytes_match_claimed", return_value=True),
        patch(
            "app.services.image_generation.attachments_repo.create_pending", AsyncMock()
        ) as pending,
        patch(
            "app.services.image_generation.attachments_repo.insert_verified_clone", AsyncMock()
        ) as clone,
        patch("app.services.image_generation.attachments_repo.link_to_message", link),
        patch("app.services.image_generation.attachments_repo.mark_verified", AsyncMock()),
        patch("app.services.image_generation.messages_repo.create", create),
    ):
        args = dict(
            user=user,
            chat_id=chat_id,
            prompt="Make it blue",
            create_user_message=not regenerate,
            reference_attachment_ids=None if regenerate else [reference_id],
        )
        if fail_link:
            with pytest.raises(ImageGenerationError):
                await generate_for_chat(Settings(), **args)
            session.commit.assert_not_awaited()
            assert gateway.delete_bytes.await_count == 2
            refund.assert_awaited_once()
        else:
            await generate_for_chat(Settings(), **args)
            session.commit.assert_awaited_once()
            gateway.delete_bytes.assert_not_awaited()
        assert load.await_args.kwargs["attachment_ids"] == [reference_id]
        assert generated.await_args.kwargs["reference_images"] == [
            (b"reference-bytes", "image/png")
        ]
        assert pending.await_args.kwargs["commit"] is False
        assert all(call.kwargs["commit"] is False for call in create.await_args_list)
        assert all(call.kwargs["commit"] is False for call in link.await_args_list)
        assert clone.await_count == int(not regenerate)
