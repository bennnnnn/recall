import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.exceptions import AttachmentValidationError
from app.gateways.storage_gateway import LocalStorageGateway
from app.models.math_schemas import MathImageExtract


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
    row.verified_at = None

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
        patch("app.services.chat.turn_prep.attachments.SessionLocal", return_value=SessionCM()),
        patch("app.services.chat.turn_prep.prepare.SessionLocal", return_value=SessionCM()),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=user)),
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


@pytest.mark.asyncio
async def test_prepare_chat_turn_threads_image_math_extract_to_prompt_context():
    """End-to-end coverage for the camera-math OCR block (zero coverage
    before this test): attaching an image + the exact camera trigger
    phrase must invoke extract_equation_from_image and pass the resulting
    structured MathImageExtract through to build_stream_prompt_context as
    image_math_extract — not just discard it after stringifying into the
    free-text content (Phase B item 6 fix)."""
    from app.services.chat.turn_prep import prepare_chat_turn

    user_id = uuid4()
    chat_id = uuid4()
    attachment_id = uuid4()
    message_id = uuid4()
    camera_prompt = "Solve the math problem in this image step by step."

    user = MagicMock()
    user.id = user_id
    chat = MagicMock()
    chat.id = chat_id
    chat.project_id = None
    chat.quiz_mode = None

    row = MagicMock()
    row.id = attachment_id
    row.content_type = "image/png"
    row.storage_key = "user/key"
    row.size_bytes = 128

    settings = Settings(attachments_enabled=True)
    redis = AsyncMock()
    session = AsyncMock()
    gateway = MagicMock(spec=LocalStorageGateway)
    extracted = MathImageExtract(lhs="f(x,2)", rhs="7", variables=["x"], found=True)
    user_message = MagicMock()
    user_message.id = message_id

    class SessionCM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args: object) -> None:
            return None

    captured: dict[str, object] = {}

    async def _fake_build_stream_prompt_context(*_args: object, **kwargs: object):
        captured["image_math_extract"] = kwargs.get("image_math_extract")
        return SimpleNamespace(
            prompt_messages=[],
            meta={},
            instant_reply=None,
            search_sources=[],
            local_places=False,
            max_out=100,
            fallback_models=[],
            minimal_quiz=False,
            minimal_vocab_answer=False,
            active_vocab_turn=False,
            lightweight=False,
            rich_context=True,
            quiz_grade=None,
            verified_math=None,
        )

    with (
        patch("app.services.chat.turn_prep.attachments.SessionLocal", return_value=SessionCM()),
        patch("app.services.chat.turn_prep.prepare.SessionLocal", return_value=SessionCM()),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=chat)),
        patch(
            "app.repositories.attachments.get_by_ids",
            AsyncMock(return_value=[row]),
        ),
        patch(
            "app.gateways.storage_gateway.get_storage_gateway",
            return_value=gateway,
        ),
        patch(
            "app.services.attachment_content.format_attachment_lines",
            AsyncMock(return_value=(["[image attached]"], True)),
        ),
        patch(
            "app.services.attachment_content.read_attachment_bytes",
            AsyncMock(return_value=b"fake-bytes"),
        ),
        patch(
            "app.services.attachment_content.inject_vision_content",
            AsyncMock(),
        ),
        patch(
            "app.services.math_image_extract.extract_equation_from_image",
            AsyncMock(return_value=extracted),
        ) as extract_mock,
        patch(
            "app.services.plan.resolve_user_model_override",
            return_value="smart-chat",
        ),
        patch(
            "app.repositories.messages.count_for_chat",
            AsyncMock(return_value=0),
        ),
        patch(
            "app.repositories.messages.create",
            AsyncMock(return_value=user_message),
        ) as create_mock,
        patch(
            "app.repositories.attachments.link_to_message",
            AsyncMock(),
        ),
        patch(
            "app.services.chat.turn_prep.prepare.build_stream_prompt_context",
            AsyncMock(side_effect=_fake_build_stream_prompt_context),
        ),
        patch(
            "app.services.chat.quiz_messages.get_last_quiz_assistant",
            AsyncMock(return_value=None),
        ),
    ):
        await prepare_chat_turn(
            user_id=user_id,
            chat_id=chat_id,
            content=camera_prompt,
            model_alias=None,
            settings=settings,
            redis=redis,
            reserved_tokens=100,
            attachment_ids=[attachment_id],
        )

    extract_mock.assert_awaited_once()
    assert captured["image_math_extract"] == extracted
    saved = create_mock.await_args.kwargs["content"]
    assert "BEGIN UNTRUSTED" not in saved
    assert "[image attached]" in saved
    assert "Extracted equation" not in saved


async def _run_prepare_chat_turn_with_caption(caption: str) -> AsyncMock:
    """Shared harness for the camera-caption-edit regression tests below —
    identical to test_prepare_chat_turn_threads_image_math_extract_to_prompt_context's
    setup, parametrized only on the sent caption text. Returns the mocked
    extract_equation_from_image so callers can assert whether OCR ran."""
    from app.services.chat.turn_prep import prepare_chat_turn

    user_id = uuid4()
    chat_id = uuid4()
    attachment_id = uuid4()
    message_id = uuid4()

    user = MagicMock()
    user.id = user_id
    chat = MagicMock()
    chat.id = chat_id
    chat.project_id = None
    chat.quiz_mode = None

    row = MagicMock()
    row.id = attachment_id
    row.content_type = "image/png"
    row.storage_key = "user/key"
    row.size_bytes = 128

    settings = Settings(attachments_enabled=True)
    redis = AsyncMock()
    session = AsyncMock()
    gateway = MagicMock(spec=LocalStorageGateway)
    extracted = MathImageExtract(lhs="2*x+3", rhs="7", variables=["x"], found=True)
    user_message = MagicMock()
    user_message.id = message_id

    class SessionCM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args: object) -> None:
            return None

    async def _fake_build_stream_prompt_context(*_args: object, **kwargs: object):
        return SimpleNamespace(
            prompt_messages=[],
            meta={},
            instant_reply=None,
            search_sources=[],
            local_places=False,
            max_out=100,
            fallback_models=[],
            minimal_quiz=False,
            minimal_vocab_answer=False,
            active_vocab_turn=False,
            lightweight=False,
            rich_context=True,
            quiz_grade=None,
            verified_math=None,
        )

    with (
        patch("app.services.chat.turn_prep.attachments.SessionLocal", return_value=SessionCM()),
        patch("app.services.chat.turn_prep.prepare.SessionLocal", return_value=SessionCM()),
        patch("app.repositories.users.get_by_id", AsyncMock(return_value=user)),
        patch("app.repositories.chats.get_by_id", AsyncMock(return_value=chat)),
        patch(
            "app.repositories.attachments.get_by_ids",
            AsyncMock(return_value=[row]),
        ),
        patch(
            "app.gateways.storage_gateway.get_storage_gateway",
            return_value=gateway,
        ),
        patch(
            "app.services.attachment_content.format_attachment_lines",
            AsyncMock(return_value=(["[image attached]"], True)),
        ),
        patch(
            "app.services.attachment_content.read_attachment_bytes",
            AsyncMock(return_value=b"fake-bytes"),
        ),
        patch(
            "app.services.attachment_content.inject_vision_content",
            AsyncMock(),
        ),
        patch(
            "app.services.math_image_extract.extract_equation_from_image",
            AsyncMock(return_value=extracted),
        ) as extract_mock,
        patch(
            "app.services.plan.resolve_user_model_override",
            return_value="smart-chat",
        ),
        patch(
            "app.repositories.messages.count_for_chat",
            AsyncMock(return_value=0),
        ),
        patch(
            "app.repositories.messages.create",
            AsyncMock(return_value=user_message),
        ),
        patch(
            "app.repositories.attachments.link_to_message",
            AsyncMock(),
        ),
        patch(
            "app.services.chat.turn_prep.prepare.build_stream_prompt_context",
            AsyncMock(side_effect=_fake_build_stream_prompt_context),
        ),
        patch(
            "app.services.chat.quiz_messages.get_last_quiz_assistant",
            AsyncMock(return_value=None),
        ),
    ):
        await prepare_chat_turn(
            user_id=user_id,
            chat_id=chat_id,
            content=caption,
            model_alias=None,
            settings=settings,
            redis=redis,
            reserved_tokens=100,
            attachment_ids=[attachment_id],
        )

    return extract_mock


@pytest.mark.asyncio
async def test_prepare_chat_turn_ocr_survives_edited_camera_caption():
    """BUG FIX regression: the OCR trigger used to require the sent text to
    be byte-for-byte identical to the preset camera caption. A user who
    edits the pre-filled composer text (adds/removes a word, autocorrect
    touches punctuation) must still get the verified OCR path as long as the
    edited caption still reads as a math ask."""
    extract_mock = await _run_prepare_chat_turn_with_caption("please solve this equation for me")
    extract_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_prepare_chat_turn_ocr_skipped_for_unrelated_caption():
    """The looser trigger must not fire vision OCR on every image attachment
    — an unrelated caption (no math keyword, not the exact camera prompt)
    should not spend a vision call on an equation that likely isn't there."""
    extract_mock = await _run_prepare_chat_turn_with_caption("here's a photo of my dog")
    extract_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_attachments_reuses_verified_bytes_for_format():
    """R2 verify downloads once; format must not re-read the same object."""
    from app.services.chat.turn_prep.attachments import _process_attachments

    user_id = uuid4()
    attachment_id = uuid4()
    user = MagicMock()
    user.id = user_id
    row = MagicMock()
    row.id = attachment_id
    row.content_type = "text/plain"
    row.storage_key = "user/doc.txt"
    row.size_bytes = 5
    row.verified_at = None
    payload = b"hello"

    settings = Settings(attachments_enabled=True)
    redis = AsyncMock()
    session = AsyncMock()
    gateway = MagicMock()  # not LocalStorageGateway → R2 verify path

    class SessionCM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *_args: object) -> None:
            return None

    format_mock = AsyncMock(return_value=(["[File: x]"], False))
    with (
        patch("app.services.chat.turn_prep.attachments.SessionLocal", return_value=SessionCM()),
        patch("app.repositories.attachments.get_by_ids", AsyncMock(return_value=[row])),
        patch(
            "app.gateways.storage_gateway.get_storage_gateway",
            return_value=gateway,
        ),
        patch(
            "app.services.attachment_content.verify_uploaded_bytes",
            AsyncMock(return_value=(payload, None)),
        ) as verify_mock,
        patch(
            "app.services.attachment_content.format_attachment_lines",
            format_mock,
        ),
        patch(
            "app.services.attachment_content.read_attachment_bytes",
            AsyncMock(return_value=b"should-not-read"),
        ) as read_mock,
    ):
        result = await _process_attachments(
            user_id=user_id,
            user=user,
            content="hi",
            attachment_ids=[attachment_id],
            settings=settings,
            redis=redis,
            on_status=None,
        )

    verify_mock.assert_awaited_once()
    assert format_mock.await_args.kwargs["data"] == payload
    assert result.bytes_by_key[row.storage_key] == payload
    read_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_attachments_skips_verify_when_already_verified():
    from datetime import UTC, datetime

    from app.services.chat.turn_prep.attachments import _process_attachments

    user_id = uuid4()
    attachment_id = uuid4()
    user = MagicMock()
    user.id = user_id
    row = MagicMock()
    row.id = attachment_id
    row.content_type = "text/plain"
    row.storage_key = "user/doc.txt"
    row.size_bytes = 5
    row.verified_at = datetime(2026, 8, 1, tzinfo=UTC)

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
        patch("app.services.chat.turn_prep.attachments.SessionLocal", return_value=SessionCM()),
        patch("app.repositories.attachments.get_by_ids", AsyncMock(return_value=[row])),
        patch(
            "app.gateways.storage_gateway.get_storage_gateway",
            return_value=gateway,
        ),
        patch(
            "app.services.attachment_content.verify_uploaded_bytes",
            AsyncMock(return_value=(b"hello", None)),
        ) as verify_mock,
        patch(
            "app.services.attachment_content.format_attachment_lines",
            AsyncMock(return_value=(["[File: x]"], False)),
        ),
        patch(
            "app.services.attachment_content.read_attachment_bytes",
            AsyncMock(return_value=b"hello"),
        ),
    ):
        await _process_attachments(
            user_id=user_id,
            user=user,
            content="hi",
            attachment_ids=[attachment_id],
            settings=settings,
            redis=redis,
            on_status=None,
        )

    verify_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_attachments_image_only_does_not_flag_document():
    """An image-only attachment must not force rich context — images use
    vision injection (runs regardless of rich_context), and RAG is gated by
    rich_context. Forcing rich for an image turn triggers status theater +
    heavy prompt building for a plain vision QA turn."""
    from datetime import UTC, datetime

    from app.services.chat.turn_prep.attachments import _process_attachments

    user_id = uuid4()
    attachment_id = uuid4()
    user = MagicMock()
    user.id = user_id
    row = MagicMock()
    row.id = attachment_id
    row.content_type = "image/png"
    row.storage_key = "user/photo.png"
    row.size_bytes = 5
    row.verified_at = datetime(2026, 8, 1, tzinfo=UTC)

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
        patch("app.services.chat.turn_prep.attachments.SessionLocal", return_value=SessionCM()),
        patch("app.repositories.attachments.get_by_ids", AsyncMock(return_value=[row])),
        patch("app.gateways.storage_gateway.get_storage_gateway", return_value=gateway),
        patch(
            "app.services.attachment_content.format_attachment_lines",
            AsyncMock(return_value=(["[Image: photo.png]"], True)),
        ),
    ):
        result = await _process_attachments(
            user_id=user_id,
            user=user,
            content="what's in this photo?",
            attachment_ids=[attachment_id],
            settings=settings,
            redis=redis,
            on_status=None,
        )

    assert result.has_image_attachment is True
    assert result.has_document_attachment is False


@pytest.mark.asyncio
async def test_process_attachments_document_flags_document():
    """A document attachment flags has_document_attachment so the turn
    forces rich context (doc RAG is gated by rich_context)."""
    from datetime import UTC, datetime

    from app.services.chat.turn_prep.attachments import _process_attachments

    user_id = uuid4()
    attachment_id = uuid4()
    user = MagicMock()
    user.id = user_id
    row = MagicMock()
    row.id = attachment_id
    row.content_type = "text/plain"
    row.storage_key = "user/notes.txt"
    row.size_bytes = 5
    row.verified_at = datetime(2026, 8, 1, tzinfo=UTC)

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
        patch("app.services.chat.turn_prep.attachments.SessionLocal", return_value=SessionCM()),
        patch("app.repositories.attachments.get_by_ids", AsyncMock(return_value=[row])),
        patch("app.gateways.storage_gateway.get_storage_gateway", return_value=gateway),
        patch(
            "app.services.attachment_content.format_attachment_lines",
            AsyncMock(return_value=(["[File: notes.txt]"], False)),
        ),
    ):
        result = await _process_attachments(
            user_id=user_id,
            user=user,
            content="summarize this",
            attachment_ids=[attachment_id],
            settings=settings,
            redis=redis,
            on_status=None,
        )

    assert result.has_image_attachment is False
    assert result.has_document_attachment is True


def _prompt_bundle() -> SimpleNamespace:
    return SimpleNamespace(
        prompt_messages=[],
        meta={},
        instant_reply=None,
        search_sources=[],
        local_places=False,
        max_out=100,
        fallback_models=[],
        minimal_quiz=False,
        minimal_vocab_answer=False,
        active_vocab_turn=False,
        lightweight=True,
        rich_context=False,
        quiz_grade=None,
        verified_math=None,
    )


@pytest.mark.asyncio
async def test_prepare_overlap_returns_before_persist_commit():
    """Prompt-ready must not wait on the Neon user-row commit."""
    from app.services.chat.turn_prep import prepare_chat_turn
    from app.services.chat.turn_prep.mode import _TurnMode

    persist_hold = asyncio.Event()
    create_started = asyncio.Event()

    async def slow_create(*_a: object, **kwargs: object) -> MagicMock:
        create_started.set()
        await persist_hold.wait()
        msg = MagicMock()
        msg.id = kwargs.get("message_id")
        return msg

    user = MagicMock()
    user.id = uuid4()
    chat = MagicMock()
    chat.id = uuid4()
    chat.project_id = None
    chat.quiz_mode = None
    chat.summary = None
    mode = _TurnMode(
        lightweight=True,
        rich_context=False,
        minimal_personal=False,
        minimal_quiz=False,
        minimal_vocab_answer=False,
        active_vocab_turn=False,
        day_planning=False,
        day_reflection=False,
    )

    class SessionCM:
        async def __aenter__(self) -> AsyncMock:
            return AsyncMock()

        async def __aexit__(self, *_args: object) -> None:
            return None

    with (
        patch("app.services.chat.turn_prep.prepare.SessionLocal", return_value=SessionCM()),
        patch("app.repositories.messages.create", side_effect=slow_create),
        patch(
            "app.services.chat.turn_prep.prepare.build_stream_prompt_context",
            AsyncMock(return_value=_prompt_bundle()),
        ),
        patch(
            "app.services.chat.quiz_messages.get_last_quiz_assistant",
            AsyncMock(return_value=None),
        ),
    ):
        ctx = await asyncio.wait_for(
            prepare_chat_turn(
                user_id=user.id,
                chat_id=chat.id,
                content="hi",
                model_alias=None,
                settings=Settings(),
                redis=AsyncMock(),
                reserved_tokens=100,
                user=user,
                chat=chat,
                turn_mode=mode,
                prior_count=0,
                recent_messages=[],
                resolved_model="free-chat",
            ),
            timeout=2,
        )
        await asyncio.wait_for(create_started.wait(), timeout=2)
        persist = ctx.user_message_persist
        assert persist is not None
        assert persist.done() is False
        persist_hold.set()
        await persist

    assert ctx.user_message_persist is persist


@pytest.mark.asyncio
async def test_await_user_message_persist_copies_indexable_ids_once():
    from app.services.chat.turn_prep import StreamContext, await_user_message_persist

    async def persist() -> list[str]:
        return ["att-1"]

    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[],
        run_title=False,
        user_message_content="hi",
        reserved_tokens=10,
        max_output_tokens=50,
        user_message_persist=asyncio.create_task(persist()),
    )
    await await_user_message_persist(ctx)
    assert ctx.indexable_attachment_ids == ["att-1"]
    assert ctx.user_message_persist is None
    await await_user_message_persist(ctx)
    assert ctx.indexable_attachment_ids == ["att-1"]
