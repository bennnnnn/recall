from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.exceptions import AttachmentValidationError


@pytest.mark.asyncio
async def test_count_image_attachments_issues_a_single_batched_query():
    from app.services.chat.turn_prep import count_image_attachments

    user_id = uuid4()
    attachment_ids = [uuid4(), uuid4(), uuid4()]
    image_row = MagicMock(content_type="image/png")
    pdf_row = MagicMock(content_type="application/pdf")
    session = AsyncMock()

    with patch(
        "app.repositories.attachments.get_by_ids",
        AsyncMock(return_value=[image_row, pdf_row]),
    ) as get_by_ids_mock:
        count = await count_image_attachments(session, user_id, attachment_ids)

    assert count == 1
    get_by_ids_mock.assert_awaited_once_with(session, attachment_ids, user_id)


@pytest.mark.asyncio
async def test_prepare_chat_turn_refunds_image_quota_when_r2_bytes_invalid():
    from app.services.chat.turn_prep import prepare_chat_turn

    user_id = uuid4()
    chat_id = uuid4()
    attachment_id = uuid4()
    user = MagicMock()
    user.id = user_id
    row = MagicMock()
    row.id = attachment_id
    row.content_type = "image/png"
    row.storage_key = "user/key"
    row.size_bytes = 128

    settings = Settings(attachments_enabled=True)
    redis = AsyncMock()
    session = AsyncMock()
    gateway = MagicMock()

    class SessionCM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args: object) -> None:
            return None

    with (
        patch("app.services.chat.turn_prep.SessionLocal", return_value=SessionCM()),
        patch("app.services.chat.users_repo.get_by_id", AsyncMock(return_value=user)),
        patch(
            "app.repositories.attachments.get_by_ids",
            AsyncMock(return_value=[row]),
        ),
        patch(
            "app.gateways.storage_gateway.get_storage_gateway",
            return_value=gateway,
        ),
        patch(
            "app.services.attachment_content.verify_uploaded_bytes",
            AsyncMock(return_value=(None, "Uploaded bytes do not match the declared content type")),
        ),
        patch(
            "app.services.attachment_content.purge_invalid_upload",
            AsyncMock(),
        ),
        patch(
            "app.services.quota.refund_image_upload",
            AsyncMock(),
        ) as refund_mock,
    ):
        with pytest.raises(AttachmentValidationError):
            await prepare_chat_turn(
                user_id=user_id,
                chat_id=chat_id,
                content="hi",
                model_alias=None,
                settings=settings,
                redis=redis,
                reserved_tokens=100,
                attachment_ids=[attachment_id],
            )

    refund_mock.assert_awaited_once_with(redis, user_id)
