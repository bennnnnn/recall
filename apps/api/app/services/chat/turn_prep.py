import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import SessionLocal
from app.exceptions import ChatNotFoundError
from app.gateways.web_search_gateway import WebSearchHit
from app.models.orm import Attachment, User
from app.services import day_planning as day_planning_service
from app.services import profile as profile_service
from app.services import projects as projects_service
from app.services import web_search as web_search_service
from app.services.chat.prompt_constants import is_broad_self_question, max_output_tokens_for_style
from app.services.context_window import estimate_tokens
from app.services.prompt_safety import wrap_untrusted

logger = logging.getLogger(__name__)

StreamStatusFn = Callable[[str], Awaitable[None]]

INTEGRATION_LOAD_TIMEOUT_SECONDS = 5.0

_T = TypeVar("_T")


async def _timed_integration_load(label: str, coro: Awaitable[_T]) -> _T | None:
    try:
        return await asyncio.wait_for(coro, timeout=INTEGRATION_LOAD_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.warning("%s integration load timed out", label)
        return None
    except Exception:
        logger.exception("%s integration load failed", label)
        return None


@dataclass
class RegenerateBackup:
    content: str
    model: str | None


@dataclass
class ClientGeoContext:
    user_location: str | None
    client_lat: float | None
    client_lng: float | None
    has_geo_fix: bool
    geo_query: bool
    ambiguous_nearby: bool
    local_places: bool


@dataclass
class StreamContext:
    user_id: UUID
    chat_id: UUID
    model: str
    prompt_messages: list[dict[str, Any]]
    run_title: bool
    user_message_content: str
    reserved_tokens: int
    max_output_tokens: int
    recalled_count: int = 0
    memory_hints: list[str] = field(default_factory=list)
    context_summarized: int = 0
    instant_reply: str | None = None
    search_sources: list[WebSearchHit] = field(default_factory=list)
    local_places: bool = False
    skip_memory_jobs: bool = False
    todos_pre_synced: bool = False
    prior_count: int = 0
    chat_project_id: UUID | None = None
    regenerate_backup: RegenerateBackup | None = None
    fallback_models: list[str] = field(default_factory=list)


@dataclass
class TurnPromptBundle:
    prompt_messages: list[dict[str, str]]
    meta: dict[str, Any]
    instant_reply: str | None
    search_sources: list[WebSearchHit]
    local_places: bool
    max_out: int
    fallback_models: list[str]
    minimal_quiz: bool
    geo: ClientGeoContext
    local_tz: str


def resolve_client_geo(
    user: User,
    content: str,
    *,
    client_location: str | None,
    client_latitude: float | None,
    client_longitude: float | None,
) -> ClientGeoContext:
    normalized_client_location = profile_service.normalize_client_location(client_location)
    client_coordinates = profile_service.normalize_client_coordinates(
        client_latitude, client_longitude
    )
    user_location = profile_service.effective_location_label(user, normalized_client_location)
    geo_query = web_search_service.is_geo_query(content)
    if geo_query:
        user_location = normalized_client_location
    client_lat = client_coordinates[0] if client_coordinates else None
    client_lng = client_coordinates[1] if client_coordinates else None
    has_geo_fix = bool(user_location) or client_coordinates is not None
    local_places = web_search_service.is_places_list_query(content)
    ambiguous_nearby = web_search_service.is_ambiguous_local_places_query(content)
    if ambiguous_nearby:
        local_places = False
    return ClientGeoContext(
        user_location=user_location,
        client_lat=client_lat,
        client_lng=client_lng,
        has_geo_fix=has_geo_fix,
        geo_query=geo_query,
        ambiguous_nearby=ambiguous_nearby,
        local_places=local_places,
    )


async def count_image_attachments(
    session: AsyncSession, user_id: UUID, attachment_ids: list[UUID]
) -> int:
    from app.repositories import attachments as attachments_repo
    from app.services.attachment_content import IMAGE_CONTENT_TYPES, normalize_content_type

    count = 0
    for attachment_id in attachment_ids:
        row = await attachments_repo.get_by_id(session, attachment_id, user_id)
        if row is None:
            continue
        if normalize_content_type(row.content_type) in IMAGE_CONTENT_TYPES:
            count += 1
    return count


def vision_reserve_tokens(settings: Settings, image_count: int) -> int:
    if image_count <= 0:
        return 0
    return image_count * settings.image_attachment_reserve_tokens


async def _load_calendar_prompt_block(
    user_id: UUID,
    redis: Redis,
    settings: Settings,
    *,
    cache_only: bool,
) -> str | None:
    import app.services.chat as chat_pkg

    async with SessionLocal() as session:
        user = await chat_pkg.users_repo.get_by_id(session, user_id)
        if user is None:
            return None
        return await chat_pkg.calendar_service.load_calendar_for_prompt(
            session,
            redis,
            user,
            settings,
            cache_only=cache_only,
        )


async def _load_gmail_prompt_block(
    user_id: UUID,
    redis: Redis,
    settings: Settings,
) -> str | None:
    import app.services.chat as chat_pkg

    async with SessionLocal() as session:
        user = await chat_pkg.users_repo.get_by_id(session, user_id)
        if user is None:
            return None
        return await chat_pkg.email_service.load_gmail_for_prompt(session, redis, user, settings)


async def _load_gmail_context_block(
    user_id: UUID,
    redis: Redis,
    settings: Settings,
) -> tuple[str, list[Any], list[Any], str | None] | None:
    import app.services.chat as chat_pkg

    async with SessionLocal() as session:
        user = await chat_pkg.users_repo.get_by_id(session, user_id)
        if user is None:
            return None
        return await chat_pkg.email_service.load_gmail_context(session, redis, user, settings)


async def build_stream_prompt_context(
    user_id: UUID,
    chat_id: UUID,
    content: str,
    model: str,
    settings: Settings,
    redis: Redis,
    *,
    client_timezone: str | None,
    client_location: str | None,
    client_latitude: float | None,
    client_longitude: float | None,
    has_image_attachment: bool = False,
    on_status: StreamStatusFn | None = None,
    todo_sync_feedback: str | None = None,
    quiz_mode: str | None = None,
) -> TurnPromptBundle:
    """Shared prompt assembly for new turns and regenerate."""
    import app.services.chat as chat_pkg

    meta: dict[str, Any] = {}
    minimal_personal = is_broad_self_question(content)
    minimal_quiz = web_search_service.is_vocab_quiz_answer(content) and quiz_mode != "chat"
    day_planning = day_planning_service.is_day_planning_question(content)
    day_reflection = day_planning_service.is_day_reflection_question(content)

    user_locale: str | None = None
    chat_summary: str | None = None
    prompt_messages: list[dict[str, str]]
    instant_reply: str | None = None
    prior_user_messages: list[str] = []
    has_calendar_write = False
    geo: ClientGeoContext
    local_tz: str
    max_out: int
    fallback_models: list[str]

    async with SessionLocal() as session:
        user = await chat_pkg.users_repo.get_by_id(session, user_id)
        if user is None:
            raise ChatNotFoundError("User not found.")
        chat = await chat_pkg.chats_repo.get_by_id(session, chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found.")

        user_locale = user.locale
        chat_summary = chat.summary
        geo = resolve_client_geo(
            user,
            content,
            client_location=client_location,
            client_latitude=client_latitude,
            client_longitude=client_longitude,
        )
        local_tz = chat_pkg.time_context_service.effective_timezone(user.timezone, client_timezone)

        if on_status is not None:
            await on_status("preparing")

        prompt_messages = await chat_pkg.build_prompt_messages(
            session,
            user,
            chat.id,
            settings,
            summary=chat_summary,
            out=meta,
            query_text=content,
            minimal_personal_context=minimal_personal,
            minimal_quiz_context=minimal_quiz,
            client_timezone=client_timezone,
            prompt_location=geo.user_location if geo.geo_query and geo.has_geo_fix else None,
            todo_sync_feedback=todo_sync_feedback,
        )

        if chat_pkg.time_context_service.is_time_question(content):
            instant_reply = chat_pkg.time_context_service.format_time_answer(local_tz, user_locale)
        elif chat_pkg.time_context_service.is_location_question(content):
            instant_reply = chat_pkg.time_context_service.format_location_answer(
                geo.user_location, local_tz
            )
        elif chat_pkg.calendar_service.is_external_calendar_question(content):
            if not await chat_pkg.calendar_service.is_connected(session, user.id):
                instant_reply = chat_pkg.calendar_service.format_not_connected_answer()
        elif chat_pkg.email_service.is_external_email_question(content):
            if not await chat_pkg.email_service.is_connected(session, user.id):
                instant_reply = chat_pkg.email_service.format_not_connected_answer()

        if (
            instant_reply is None
            and not minimal_personal
            and not minimal_quiz
            and not day_planning
            and not geo.ambiguous_nearby
            and not chat_pkg.calendar_service.is_external_calendar_question(content)
            and not chat_pkg.email_service.is_external_email_question(content)
        ):
            prior_user_messages = await chat_pkg.messages_repo.recent_user_contents(
                session, chat.id
            )

        if (
            instant_reply is None
            and not minimal_personal
            and not minimal_quiz
            and not day_planning
            and not geo.ambiguous_nearby
            and not chat_pkg.calendar_service.is_external_calendar_question(content)
            and not chat_pkg.email_service.is_external_email_question(content)
        ):
            has_calendar_write = await chat_pkg.calendar_service.has_write_access(session, user.id)

        if (
            not settings.mcp_tools_enabled
            and chat_pkg.calendar_service.is_calendar_create_request(content)
            and instant_reply is None
        ):
            if not has_calendar_write:
                has_calendar_write = await chat_pkg.calendar_service.has_write_access(
                    session, user.id
                )

        max_out = (
            max_output_tokens_for_style("short", settings)
            if minimal_quiz
            else max_output_tokens_for_style(user.response_style, settings)
        )
        fallback_models = chat_pkg.plan_service.chat_fallback_models(user, settings, model)

        await session.commit()

    # DB connection released before external integration / web search I/O.
    gmail_context: tuple[str, list[Any], list[Any], str | None] | None = None
    if instant_reply is None and geo.geo_query and not geo.has_geo_fix:
        instant_reply = web_search_service.format_location_not_set_answer()

    if instant_reply is None and chat_pkg.email_service.is_external_email_question(content):
        async with SessionLocal() as session:
            connected = await chat_pkg.email_service.is_connected(session, user_id)
        if connected:
            if on_status is not None:
                await on_status("checking_inbox")
            gmail_context = await _load_gmail_context_block(user_id, redis, settings)

    local_places = geo.local_places
    if instant_reply is None and not minimal_personal and not minimal_quiz:
        integration_blocks: list[str] = []
        load_calendar = chat_pkg.calendar_service.should_inject_calendar_block(content)
        load_gmail = chat_pkg.email_service.should_inject_gmail_block(content)
        calendar_block: str | None = None
        gmail_block: str | None = None

        pending: list[tuple[str, Awaitable[str | None]]] = []
        if load_calendar:
            if on_status is not None:
                await on_status("loading_calendar")
            pending.append(
                (
                    "calendar",
                    _timed_integration_load(
                        "calendar",
                        _load_calendar_prompt_block(
                            user_id,
                            redis,
                            settings,
                            cache_only=day_reflection,
                        ),
                    ),
                )
            )
        if gmail_context is not None:
            google_email, messages, pending_suggestions, fetch_error = gmail_context
            gmail_block = chat_pkg.email_service.format_gmail_block(
                google_email=google_email,
                messages=messages,
                pending_suggestions=pending_suggestions,
                fetch_error=fetch_error,
            )
        elif load_gmail:
            if on_status is not None:
                await on_status("checking_inbox")
            pending.append(
                (
                    "gmail",
                    _timed_integration_load(
                        "gmail",
                        _load_gmail_prompt_block(user_id, redis, settings),
                    ),
                )
            )

        if pending:
            results = await asyncio.gather(*(task for _, task in pending))
            for (label, _), result in zip(pending, results, strict=True):
                if label == "calendar":
                    calendar_block = result
                elif label == "gmail":
                    gmail_block = result

        if calendar_block:
            integration_blocks.append(wrap_untrusted("calendar", calendar_block))
        if gmail_block:
            integration_blocks.append(wrap_untrusted("gmail", gmail_block))
            if chat_pkg.email_service.is_external_email_question(content):
                integration_blocks.append(chat_pkg.email_service.GMAIL_INBOX_ANSWER_HINT)
        if (
            not settings.mcp_tools_enabled
            and chat_pkg.calendar_service.is_calendar_create_request(content)
            and has_calendar_write
        ):
            integration_blocks.append(chat_pkg.calendar_service.CALENDAR_WRITE_HINT)
        if integration_blocks:
            prompt_messages[0] = {
                "role": "system",
                "content": f"{prompt_messages[0]['content']}\n\n" + "\n\n".join(integration_blocks),
            }

    search_sources: list[WebSearchHit] = []
    if (
        instant_reply is None
        and not minimal_personal
        and not minimal_quiz
        and not day_planning
        and not geo.ambiguous_nearby
        and not chat_pkg.calendar_service.is_external_calendar_question(content)
        and not chat_pkg.email_service.is_external_email_question(content)
    ):
        async with SessionLocal() as session:
            user = await chat_pkg.users_repo.get_by_id(session, user_id)
            if user is None:
                raise ChatNotFoundError("User not found.")
        prompt_messages, search_sources = await chat_pkg._augment_web_and_tools(
            prompt_messages,
            content,
            settings,
            user_timezone=local_tz,
            user_location=geo.user_location,
            latitude=geo.client_lat,
            longitude=geo.client_lng,
            prior_user_messages=prior_user_messages,
            has_image_attachment=has_image_attachment,
            on_status=on_status,
            user=user,
            redis=redis,
            has_calendar_write=has_calendar_write,
        )

    return TurnPromptBundle(
        prompt_messages=prompt_messages,
        meta=meta,
        instant_reply=instant_reply,
        search_sources=search_sources,
        local_places=local_places,
        max_out=max_out,
        fallback_models=fallback_models,
        minimal_quiz=minimal_quiz,
        geo=geo,
        local_tz=local_tz,
    )


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
) -> StreamContext:
    import app.services.chat as chat_pkg

    user_content = content
    gateway = None
    has_image_attachment = False
    image_attachments: list[tuple[str, str]] = []

    if attachment_ids and settings.attachments_enabled:
        async with SessionLocal() as session:
            user = await chat_pkg.users_repo.get_by_id(session, user_id)
            if user is None:
                raise ChatNotFoundError("User not found.")
            from app.repositories import attachments as attachments_repo

            attachment_rows: list[Attachment] = []
            for attachment_id in attachment_ids:
                row = await attachments_repo.get_by_id(session, attachment_id, user.id)
                if row is not None:
                    attachment_rows.append(row)

        if attachment_rows:
            from app.gateways.storage_gateway import LocalStorageGateway, get_storage_gateway
            from app.services import attachment_content as attachment_content_service

            gateway = get_storage_gateway(settings)
            if not isinstance(gateway, LocalStorageGateway):
                from app.exceptions import AttachmentValidationError

                for row in attachment_rows:
                    _, error = await attachment_content_service.verify_uploaded_bytes(
                        gateway,
                        content_type=row.content_type,
                        storage_key=row.storage_key,
                    )
                    if error:
                        if attachment_content_service.is_image_content_type(row.content_type):
                            from app.services import quota as quota_service

                            await quota_service.refund_image_upload(redis, user_id)
                        async with SessionLocal() as purge_session:
                            await attachment_content_service.purge_invalid_upload(
                                gateway,
                                purge_session,
                                attachment_id=row.id,
                                storage_key=row.storage_key,
                            )
                        raise AttachmentValidationError(error)
            attachment_lines: list[str] = []
            for row in attachment_rows:
                lines, is_image = await attachment_content_service.format_attachment_lines(
                    gateway,
                    attachment_id=str(row.id),
                    content_type=row.content_type,
                    storage_key=row.storage_key,
                    size_bytes=row.size_bytes,
                )
                if is_image:
                    has_image_attachment = True
                    image_attachments.append((row.content_type, row.storage_key))
                attachment_lines.extend(lines)
            if attachment_lines:
                if user_content.strip():
                    user_content = f"{user_content}\n\n" + "\n".join(attachment_lines)
                else:
                    user_content = "\n".join(attachment_lines)

    async with SessionLocal() as session:
        user = await chat_pkg.users_repo.get_by_id(session, user_id)
        if user is None:
            raise ChatNotFoundError("User not found.")

        chat = await chat_pkg.chats_repo.get_by_id(session, chat_id, user_id)
        if chat is None:
            raise ChatNotFoundError("Chat not found.")

        model = chat_pkg.plan_service.resolve_user_model_override(
            user, model_alias, content, settings
        )
        if attachment_ids and settings.attachments_enabled and has_image_attachment:
            model = "vision-chat"

        prior_count = await chat_pkg.messages_repo.count_for_chat(session, chat_id)

        user_message = await chat_pkg.messages_repo.create(
            session,
            chat_id=chat_id,
            user_id=user.id,
            role="user",
            content=user_content,
            model=model,
            input_tokens=estimate_tokens(user_content),
        )
        is_letter_answer = web_search_service.is_vocab_quiz_answer(content)
        minimal_quiz = is_letter_answer and getattr(chat, "quiz_mode", None) != "chat"
        if is_letter_answer and minimal_quiz and chat.project_id is not None:
            prior_assistant = await chat_pkg.messages_repo.get_last_assistant(session, chat_id)
            if prior_assistant is not None:
                try:
                    await projects_service.apply_deterministic_quiz_answer(
                        session,
                        user_id=user.id,
                        chat_id=chat_id,
                        project_id=chat.project_id,
                        assistant_content=prior_assistant.content,
                        user_answer=content,
                    )
                except Exception:
                    logger.exception(
                        "Failed to record quiz answer for user_id=%s chat_id=%s",
                        user.id,
                        chat_id,
                    )
        if attachment_ids and settings.attachments_enabled:
            from app.repositories import attachments as attachments_repo

            await attachments_repo.link_to_message(
                session,
                user_id=user.id,
                attachment_ids=attachment_ids,
                message_id=user_message.id,
            )

        chat_project_id = chat.project_id
        quiz_mode = getattr(chat, "quiz_mode", None)

        await session.commit()

    todo_sync_feedback: str | None = None
    todos_pre_synced = False
    if not web_search_service.is_vocab_quiz_answer(content):
        sync_transcript: str | None = None
        should_sync = False
        async with SessionLocal() as session:
            recent_for_sync = await chat_pkg.messages_repo.list_recent(session, chat_id, limit=8)
            sync_transcript = chat_pkg.todos_service.format_chat_transcript(recent_for_sync)
            should_sync = chat_pkg.todos_service.should_pre_sync_todos(content, sync_transcript)
            await session.commit()

        if should_sync and sync_transcript is not None:
            feedback = await chat_pkg.todos_service.sync_todos_before_reply(
                settings,
                user_id=user_id,
                chat_id=chat_id,
                transcript=sync_transcript,
            )
            todos_pre_synced = True
            todo_sync_feedback = chat_pkg.todos_service.format_todo_sync_feedback(feedback)

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
        on_status=on_status,
        todo_sync_feedback=todo_sync_feedback,
        quiz_mode=quiz_mode,
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

    return StreamContext(
        user_id=user_id,
        chat_id=chat_id,
        model=model,
        prompt_messages=prompt_messages,
        run_title=prior_count == 0,
        user_message_content=content,
        reserved_tokens=reserved_tokens,
        max_output_tokens=bundle.max_out,
        recalled_count=int(bundle.meta.get("recalled") or 0),
        memory_hints=list(bundle.meta.get("memory_hints") or []),
        context_summarized=int(bundle.meta.get("context_summarized") or 0),
        instant_reply=bundle.instant_reply,
        search_sources=bundle.search_sources,
        local_places=bundle.local_places,
        skip_memory_jobs=bundle.minimal_quiz,
        todos_pre_synced=todos_pre_synced,
        prior_count=prior_count,
        chat_project_id=chat_project_id,
        fallback_models=bundle.fallback_models,
    )
