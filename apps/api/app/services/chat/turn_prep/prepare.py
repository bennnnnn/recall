import logging
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.exceptions import ChatNotFoundError
from app.models.orm import User
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import users as users_repo
from app.services import plan as plan_service
from app.services import projects as projects_service
from app.services import web_search as web_search_service
from app.services.chat.stream_status import StreamStatusFn
from app.services.chat.turn_prep.attachments import _process_attachments
from app.services.chat.turn_prep.context import (
    StreamContext,
    build_stream_prompt_context,
    stream_context_from_bundle,
)
from app.services.chat.turn_timing import TurnTimingTracker
from app.services.context_window import estimate_tokens
from app.services.vocab_quiz import QuizAnswerGrade

logger = logging.getLogger(__name__)


async def _grade_quiz_answer(
    session: AsyncSession,
    *,
    user: User,
    chat_id: UUID,
    chat_project_id: UUID | None,
    content: str,
) -> tuple[bool, QuizAnswerGrade | None]:
    """Deterministically grade a letter/choice quiz answer when a project is linked."""

    is_letter_answer = False
    quiz_grade: QuizAnswerGrade | None = None
    if chat_project_id is not None:
        from app.services import vocab_quiz as vocab_quiz_service
        from app.services.chat.quiz_messages import (
            count_quiz_letter_answers_since,
            get_last_quiz_assistant,
        )

        prior_assistant = await get_last_quiz_assistant(session, chat_id)
        quiz_choices: tuple[tuple[str, str], ...] | None = None
        if prior_assistant is not None:
            parsed = vocab_quiz_service.parse_vocab_quiz(prior_assistant.content)
            if parsed is not None:
                quiz_choices = parsed.choices
        is_letter_answer = vocab_quiz_service.is_vocab_quiz_answer(content, choices=quiz_choices)
        if is_letter_answer and prior_assistant is not None:
            try:
                attempt = await count_quiz_letter_answers_since(
                    session,
                    chat_id,
                    after=prior_assistant.created_at,
                    choices=quiz_choices,
                )
                quiz_grade = await projects_service.apply_deterministic_quiz_answer(
                    session,
                    user_id=user.id,
                    chat_id=chat_id,
                    project_id=chat_project_id,
                    assistant_content=prior_assistant.content,
                    user_answer=content,
                    attempt=max(1, attempt),
                )
                if quiz_grade is None:
                    logger.warning(
                        "Quiz answer not recorded (no gradeable fence) user_id=%s chat_id=%s",
                        user.id,
                        chat_id,
                    )
            except Exception:
                logger.exception(
                    "Failed to record quiz answer for user_id=%s chat_id=%s",
                    user.id,
                    chat_id,
                )
    elif web_search_service.is_vocab_quiz_answer(content):
        logger.warning(
            "Quiz letter answer without project_id — not recorded chat_id=%s",
            chat_id,
        )
    return is_letter_answer, quiz_grade


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
    user = attachments.user
    user_content = attachments.user_content
    content = attachments.content
    has_image_attachment = attachments.has_image_attachment
    image_attachments = attachments.image_attachments
    image_math_extract = attachments.image_math_extract
    gateway = attachments.gateway

    async with SessionLocal() as session:
        if user is None:
            user = await users_repo.get_by_id(session, user_id)
            if user is None:
                raise ChatNotFoundError("User not found.")

        chat = await chats_repo.get_by_id(session, chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found.")

        model = plan_service.resolve_user_model_override(user, model_alias, content, settings)
        if attachment_ids and settings.attachments_enabled and has_image_attachment:
            model = "vision-chat"

        prior_count = await messages_repo.count_for_chat(session, chat_id)
        chat_project_id = chat.project_id
        quiz_mode = getattr(chat, "quiz_mode", None)

        user_message = await messages_repo.create(
            session,
            chat_id=chat_id,
            user_id=user.id,
            role="user",
            content=user_content,
            model=model,
            input_tokens=estimate_tokens(user_content),
            commit=False,
        )
        is_letter_answer, quiz_grade = await _grade_quiz_answer(
            session,
            user=user,
            chat_id=chat_id,
            chat_project_id=chat_project_id,
            content=content,
        )
        indexable_attachment_ids: list[str] = []
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
                indexable = await attachments_repo.get_by_ids(session, attachment_ids, user.id)
                indexable_attachment_ids = [
                    str(row.id)
                    for row in indexable
                    if attachment_rag_service.is_indexable_attachment(row)
                ]

        await session.commit()
        if quiz_grade is not None:
            await projects_service._invalidate_home_for_user(user.id)

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
    )

    prompt_messages = bundle.prompt_messages
    if has_image_attachment and image_attachments and gateway is not None:
        from app.services import attachment_content as attachment_content_service

        await attachment_content_service.inject_vision_content(
            prompt_messages,
            gateway,
            image_attachments,
            caption=content,
        )

    # Vision may have mutated prompt_messages in place on the bundle.
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
    )
