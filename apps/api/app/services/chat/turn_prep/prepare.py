import asyncio
import logging
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.ids import uuid7
from app.exceptions import ChatNotFoundError
from app.models.orm import Chat, Message, User
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import users as users_repo
from app.services import plan as plan_service
from app.services.chat.stream_status import StreamStatusFn
from app.services.chat.turn_prep.attachments import _process_attachments
from app.services.chat.turn_prep.context import (
    StreamContext,
    TurnPromptBundle,
    build_stream_prompt_context,
    stream_context_from_bundle,
)
from app.services.chat.turn_prep.mode import _classify_turn_mode, _TurnMode
from app.services.chat.turn_timing import TurnTimingTracker
from app.services.context_window import estimate_tokens
from app.services.projects.common import _invalidate_home_for_user
from app.services.prompt_safety import messages_have_attachment_marker
from app.services.vocab_quiz import QuizAnswerGrade

logger = logging.getLogger(__name__)


def _should_use_vision_chat(
    *,
    settings: Settings,
    has_image_attachment: bool,
    recent_messages: list[Any] | None,
) -> bool:
    if not settings.attachments_enabled:
        return False
    if has_image_attachment:
        return True
    if not recent_messages:
        return False
    from app.services.attachment_content import history_has_image_marker

    return history_has_image_marker(recent_messages)


async def _grade_quiz_answer(
    *,
    user: User,
    chat_id: UUID,
    chat_project_id: UUID | None,
    content: str,
    prior_assistant: Message | None = None,
) -> tuple[bool, QuizAnswerGrade | None]:
    """Chat does not grade A-D. Lesson play records mastery."""
    _ = (user, chat_id, chat_project_id, content, prior_assistant)
    return False, None


async def _maybe_invalidate_home_after_quiz(
    *,
    user_id: UUID,
    chat_project_id: UUID | None,
    is_letter_answer: bool,
    quiz_grade: QuizAnswerGrade | None,
    quiz_assistant: Message | None,
) -> None:
    if quiz_grade is not None:
        await _invalidate_home_for_user(user_id)
    elif chat_project_id is not None and is_letter_answer and quiz_assistant is not None:
        # LANG-CACHE-001: even when deterministic grading returned None (e.g.
        # open-ended vocab answer, missing fence, or no project match), the
        # background project sync may still record mastery/learning. Invalidate
        # home cache now so the next home fetch is fresh after the turn.
        await _invalidate_home_for_user(user_id)


async def prepare_chat_turn(
    *,
    user_id: UUID,
    chat_id: UUID,
    content: str,
    model_alias: str | None,
    settings: Settings,
    redis: Redis,
    reserved_tokens: int,
    attachment_ids: list[UUID] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
    on_status: StreamStatusFn | None = None,
    user: User | None = None,
    timing: TurnTimingTracker | None = None,
    chat: Chat | None = None,
    turn_mode: _TurnMode | None = None,
    prior_count: int | None = None,
    recent_messages: list[Any] | None = None,
    resolved_model: str | None = None,
) -> StreamContext:
    attachments = await _process_attachments(
        user_id=user_id,
        user=user,
        content=content,
        attachment_ids=attachment_ids,
        settings=settings,
        redis=redis,
        on_status=on_status,
    )
    if attachments.resolved_attachment_ids is not None:
        attachment_ids = attachments.resolved_attachment_ids
    user = attachments.user
    user_content = attachments.user_content
    content = attachments.content
    has_image_attachment = attachments.has_image_attachment
    image_attachments = attachments.image_attachments
    image_math_extract = attachments.image_math_extract
    gateway = attachments.gateway
    attachment_bytes_by_key = attachments.bytes_by_key

    overlap = (
        user is not None
        and chat is not None
        and turn_mode is not None
        and prior_count is not None
        and recent_messages is not None
    )
    pending_id = uuid7()
    model = resolved_model
    indexable_attachment_ids: list[str] = []
    persist_task: asyncio.Task[list[str]] | None = None
    chat_project_id: UUID | None = chat.project_id if chat is not None else None
    quiz_mode = getattr(chat, "quiz_mode", None) if chat is not None else None

    async def _persist_user_message() -> list[str]:
        nonlocal user, chat, model, prior_count, turn_mode
        nonlocal chat_project_id, quiz_mode
        indexable: list[str] = []
        if timing is not None:
            timing.mark_phase("persist_start")
        async with SessionLocal() as session:
            if user is None:
                user = await users_repo.get_by_id(session, user_id)
                if user is None:
                    raise ChatNotFoundError("User not found.")
            if chat is None:
                chat = await chats_repo.get_by_id(session, chat_id, user_id)
                if chat is None:
                    raise ChatNotFoundError("Chat not found.")
            if model is None:
                model = plan_service.resolve_user_model_override(
                    user, model_alias, content, settings
                )
            if _should_use_vision_chat(
                settings=settings,
                has_image_attachment=has_image_attachment,
                recent_messages=recent_messages,
            ):
                model = "vision-chat"
            if prior_count is None:
                prior_count = await messages_repo.count_for_chat(session, chat_id)
            chat_project_id = chat.project_id
            quiz_mode = getattr(chat, "quiz_mode", None)
            if turn_mode is None:
                turn_mode = await _classify_turn_mode(session, chat, content)
            user_message = await messages_repo.create(
                session,
                chat_id=chat_id,
                user_id=user.id,
                role="user",
                content=user_content,
                model=model,
                input_tokens=estimate_tokens(user_content),
                commit=False,
                message_id=pending_id,
            )
            if attachment_ids and settings.attachments_enabled:
                from app.repositories import attachments as attachments_repo
                from app.services import attachment_rag as attachment_rag_service

                await attachments_repo.link_to_message(
                    session,
                    user_id=user.id,
                    attachment_ids=attachment_ids,
                    message_id=user_message.id,
                )
                if settings.attachment_rag_enabled:
                    indexable_rows = await attachments_repo.get_by_ids(
                        session, attachment_ids, user.id
                    )
                    indexable = [
                        str(row.id)
                        for row in indexable_rows
                        if attachment_rag_service.is_indexable_attachment(row)
                    ]
            await session.commit()
        if timing is not None:
            timing.mark_phase("persist_done")
        return indexable

    if (
        overlap
        and user is not None
        and chat is not None
        and turn_mode is not None
        and prior_count is not None
        and recent_messages is not None
    ):
        overlap_model: str = (
            model
            if model is not None
            else plan_service.resolve_user_model_override(user, model_alias, content, settings)
        )
        if _should_use_vision_chat(
            settings=settings,
            has_image_attachment=has_image_attachment,
            recent_messages=recent_messages,
        ):
            overlap_model = "vision-chat"
        model = overlap_model
        prompt_recent = [
            *recent_messages,
            SimpleNamespace(id=pending_id, role="user", content=user_content),
        ]
        window = settings.recent_message_window
        probe = (
            bool(attachment_ids)
            or messages_have_attachment_marker(prompt_recent)
            or prior_count >= window
        )
        is_letter_answer, quiz_grade = await _grade_quiz_answer(
            user=user,
            chat_id=chat_id,
            chat_project_id=chat_project_id,
            content=content,
            prior_assistant=turn_mode.quiz_assistant,
        )
        await _maybe_invalidate_home_after_quiz(
            user_id=user.id,
            chat_project_id=chat_project_id,
            is_letter_answer=is_letter_answer,
            quiz_grade=quiz_grade,
            quiz_assistant=turn_mode.quiz_assistant,
        )

        async def _prompt() -> TurnPromptBundle:
            return await build_stream_prompt_context(
                user_id,
                chat_id,
                content,
                overlap_model,
                settings,
                redis,
                client_timezone=client_timezone,
                client_location=client_location,
                client_latitude=client_latitude,
                client_longitude=client_longitude,
                has_image_attachment=has_image_attachment,
                image_math_extract=image_math_extract,
                on_status=on_status,
                quiz_mode=quiz_mode,
                user=user,
                chat=chat,
                timing=timing,
                quiz_grade=quiz_grade,
                force_rich_context=attachments.has_document_attachment,
                turn_mode=turn_mode,
                probe_attachment_rag=probe,
                recent_messages=prompt_recent,
            )

        persist_task = asyncio.create_task(_persist_user_message())
        try:
            bundle = await _prompt()
        except BaseException:
            try:
                await persist_task
            except Exception:
                logger.exception(
                    "User message persist failed after prompt error chat_id=%s",
                    chat_id,
                )
            raise
    else:
        indexable_attachment_ids = await _persist_user_message()
        if user is None or model is None:
            raise ChatNotFoundError("User not found.")
        is_letter_answer, quiz_grade = await _grade_quiz_answer(
            user=user,
            chat_id=chat_id,
            chat_project_id=chat_project_id,
            content=content,
            prior_assistant=turn_mode.quiz_assistant if turn_mode is not None else None,
        )
        await _maybe_invalidate_home_after_quiz(
            user_id=user.id,
            chat_project_id=chat_project_id,
            is_letter_answer=is_letter_answer,
            quiz_grade=quiz_grade,
            quiz_assistant=turn_mode.quiz_assistant if turn_mode is not None else None,
        )
        bundle = await build_stream_prompt_context(
            user_id,
            chat_id,
            content,
            model,
            settings,
            redis,
            client_timezone=client_timezone,
            client_location=client_location,
            client_latitude=client_latitude,
            client_longitude=client_longitude,
            has_image_attachment=has_image_attachment,
            image_math_extract=image_math_extract,
            on_status=on_status,
            quiz_mode=quiz_mode,
            user=user,
            chat=chat,
            timing=timing,
            quiz_grade=quiz_grade,
            force_rich_context=attachments.has_document_attachment,
            turn_mode=turn_mode,
            probe_attachment_rag=bool(attachment_ids) or (prior_count or 0) > 0,
        )

    prompt_messages = bundle.prompt_messages
    from app.services import attachment_content as attachment_content_service

    if has_image_attachment and image_attachments and gateway is not None:
        await attachment_content_service.inject_vision_content(
            prompt_messages,
            gateway,
            image_attachments,
            caption=content,
            bytes_by_key=attachment_bytes_by_key,
        )
    elif not has_image_attachment and settings.attachments_enabled and user is not None:
        prior_ids = attachment_content_service.prior_image_attachment_ids(prompt_messages)
        if prior_ids:
            from app.gateways.storage_gateway import get_storage_gateway
            from app.repositories import attachments as attachments_repo

            rehydrate_gateway = gateway or get_storage_gateway(settings)
            async with SessionLocal() as session:
                rows = await attachments_repo.get_by_ids(session, prior_ids, user.id)
            by_id = {row.id: row for row in rows}
            images: list[tuple[str, str]] = []
            for uid in prior_ids:
                row = by_id.get(uid)
                if row is None or not attachment_content_service.is_image_content_type(
                    row.content_type
                ):
                    continue
                images.append((row.content_type, row.storage_key))
            injected = False
            if images:
                injected = await attachment_content_service.inject_vision_content(
                    prompt_messages,
                    rehydrate_gateway,
                    images,
                    caption=content,
                )
                if injected:
                    model = "vision-chat"
            if not injected or len(images) < len(prior_ids):
                attachment_content_service.append_image_unavailable_note(prompt_messages)

    # Vision may have mutated prompt_messages in place on the bundle.
    if user is None or chat is None or model is None or prior_count is None:
        raise ChatNotFoundError("Turn context incomplete.")
    return stream_context_from_bundle(
        bundle,
        user_id=user_id,
        chat_id=chat_id,
        model=model,
        user_message_content=content,
        reserved_tokens=reserved_tokens,
        user=user,
        prior_count=prior_count,
        chat_project_id=chat_project_id,
        timing=timing,
        is_letter_answer=is_letter_answer,
        indexable_attachment_ids=indexable_attachment_ids,
        user_message_persist=persist_task,
    )
