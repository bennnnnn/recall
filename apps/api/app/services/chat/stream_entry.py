import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.exceptions import ChatNotFoundError, ChatServiceError, QuotaExceededError
from app.models.orm import User
from app.services.chat.prompt_builder import StreamReasoningFn, StreamStatusFn
from app.services.chat.turn_prep import RegenerateBackup
from app.services.chat.turn_prep.mode import _classify_turn_mode
from app.services.chat.turn_timing import TurnTimingTracker


async def try_image_gen_for_turn(
    seams: Any,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    content: str,
    result: dict[str, Any] | None,
    create_user_message: bool,
    replace_assistant_id: UUID | None = None,
) -> bool:
    if not seams.plan_service.is_pro(user):
        return False
    image_prompt = seams.extract_image_gen_prompt(content)
    if not image_prompt:
        trimmed = content.strip()
        if not trimmed or len(trimmed) > 120 or len(trimmed.split()) > 8:
            return False
        async with seams.SessionLocal() as session:
            recent = await seams.messages_repo.list_recent(session, chat_id, limit=20)
        last_image_only, previous_subject = seams.image_gen_revision_context(recent)
        image_prompt = seams.extract_image_revision_prompt(
            content,
            last_assistant_is_image_only=last_image_only,
            previous_subject=previous_subject,
        )
    if not image_prompt:
        return False
    try:
        _user_msg, asst_msg = await seams.image_generation_service.generate_for_chat(
            settings,
            user=user,
            chat_id=chat_id,
            prompt=image_prompt,
            user_message_content=(content.strip() if create_user_message else None),
            create_user_message=create_user_message,
        )
    except seams.image_generation_service.ImageGenerationError as exc:
        if exc.status_code == 429:
            raise QuotaExceededError(exc.detail) from exc
        if exc.status_code in (403, 404):
            return False
        raise ChatServiceError(exc.detail) from exc

    if replace_assistant_id is not None:
        async with seams.SessionLocal() as session:
            old = await seams.messages_repo.get_by_id(session, replace_assistant_id, chat_id)
            if old is not None and old.role == "assistant":
                await seams.attachment_lifecycle.purge_attachments_for_messages(
                    session, settings, [old.id]
                )
                await seams.messages_repo.delete_message(session, old)
    if result is not None:
        result["message_id"] = str(asst_msg.id)
        result["final_content"] = asst_msg.content
        result["resolved_model"] = asst_msg.model or "image-gen-model"
    return True


async def stream_chat_response(
    seams: Any,
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    content: str,
    model_alias: str | None = None,
    attachment_ids: list[UUID] | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, Any] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
    user: User | None = None,
    skip_usage_seed: bool = False,
    resources: Any | None = None,
) -> AsyncIterator[str]:
    content = content.strip()
    if not content and not attachment_ids:
        raise ChatNotFoundError("Message cannot be empty.")
    timing = TurnTimingTracker()
    timing.mark_phase("turn_start")
    status = seams.wrap_stream_status(timing, on_status)

    async with seams.turn_resources(
        redis,
        user_id=user_id,
        chat_id=chat_id,
        borrowed=resources,
    ) as res:

        async def _load_user_and_quota() -> tuple[User, int, str]:
            loaded = user
            async with seams.SessionLocal() as session:
                if loaded is None:
                    loaded = await seams.users_repo.get_by_id(session, user_id)
                    if loaded is None:
                        raise ChatNotFoundError("User not found.")
                if not skip_usage_seed:
                    await seams.seed_usage_from_db(redis, session, user_id)
                limit = seams.quota_service.daily_limit_for_user(loaded, settings)
                resolved = seams.plan_service.resolve_user_model_override(
                    loaded, model_alias, content, settings
                )
            return loaded, limit, resolved

        _, (user, daily_limit, model) = await asyncio.gather(
            seams.wait_for_pending_finalize(chat_id, redis),
            _load_user_and_quota(),
        )

        if not attachment_ids and await seams._try_image_gen_for_turn(
            settings,
            user=user,
            chat_id=chat_id,
            content=content,
            result=result,
            create_user_message=True,
        ):
            await res.refund()
            return
        if res.reserved_tokens <= 0:
            vision_extra = 0
            if attachment_ids:
                async with seams.SessionLocal() as session:
                    image_count = await seams.count_image_attachments(
                        session, user_id, attachment_ids
                    )
                vision_extra = seams.vision_reserve_tokens(settings, image_count)
            await res.reserve(
                user=user,
                content=content,
                model=model,
                settings=settings,
                daily_limit=daily_limit,
                vision_extra=vision_extra,
                max_output=settings.max_output_tokens,
                seed=False,
            )
        ctx = await seams.prepare_chat_turn(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            model_alias=model_alias,
            settings=settings,
            redis=redis,
            reserved_tokens=res.reserved_tokens,
            attachment_ids=attachment_ids or [],
            client_timezone=client_timezone,
            client_location=client_location,
            client_latitude=client_latitude,
            client_longitude=client_longitude,
            on_status=status,
            user=user,
            timing=timing,
        )
        await seams._top_up_reserve_for_prompt(
            res, settings=settings, ctx=ctx, daily_limit=daily_limit
        )
        async for token in seams._yield_with_chatprep_refresh(
            redis,
            res.lock_key,
            res.lock_token,
            seams.stream_and_finalize(
                redis,
                settings,
                ctx,
                should_cancel=should_cancel,
                result=result,
                on_status=status,
                on_reasoning=on_reasoning,
                resources=res,
            ),
        ):
            yield token


async def stream_regenerate_response(
    seams: Any,
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    model_alias: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, Any] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
) -> AsyncIterator[str]:
    timing = TurnTimingTracker()
    timing.mark_phase("turn_start")
    status = seams.wrap_stream_status(timing, on_status)
    async with seams.turn_resources(redis, user_id=user_id, chat_id=chat_id) as res:
        # Last-message reads must see the committed assistant. Overlapping
        # that load with wait_for_pending_finalize can regenerate from a
        # stale last row. New turns gather wait with user/quota instead —
        # prepare reads messages only after both finish.
        await seams.wait_for_pending_finalize(chat_id, redis)
        regenerate_backup: RegenerateBackup | None = None
        omit_message_ids: set[UUID] | None = None
        async with seams.SessionLocal() as session:
            user = await seams.users_repo.get_by_id(session, user_id)
            if user is None:
                raise ChatNotFoundError("User not found.")
            chat = await seams.chats_repo.get_by_id(session, chat_id, user_id)
            if chat is None:
                raise ChatNotFoundError("Chat not found.")
            last = await seams.messages_repo.get_last(session, chat_id)
            if last is None:
                raise ChatNotFoundError("No messages to regenerate.")
            last_user = await seams.messages_repo.get_last_user(session, chat_id)
            if last_user is None:
                raise ChatNotFoundError("No user message to regenerate from.")
            model = seams.plan_service.resolve_regenerate_model(
                user, model_alias, last_user.content, last.model, settings
            )
            user_message_content = last_user.content
            prior_count = await seams.messages_repo.count_for_chat(session, chat_id)
            if last.role == "assistant":
                regenerate_backup = RegenerateBackup(
                    content=last.content,
                    model=last.model,
                    message_id=last.id,
                )
                omit_message_ids = {last.id}
            turn_mode = await _classify_turn_mode(session, chat, user_message_content)

        if await seams._try_image_gen_for_turn(
            settings,
            user=user,
            chat_id=chat_id,
            content=user_message_content,
            result=result,
            create_user_message=False,
            replace_assistant_id=(
                regenerate_backup.message_id if regenerate_backup is not None else None
            ),
        ):
            return
        await res.reserve(
            user=user,
            content=user_message_content,
            model=model,
            settings=settings,
            max_output=settings.max_output_tokens,
            seed=True,
        )
        bundle = await seams.build_stream_prompt_context(
            user_id,
            chat_id,
            user_message_content,
            model,
            settings,
            redis,
            client_timezone=client_timezone,
            client_location=client_location,
            client_latitude=client_latitude,
            client_longitude=client_longitude,
            on_status=status,
            user=user,
            chat=chat,
            timing=timing,
            omit_message_ids=omit_message_ids,
            turn_mode=turn_mode,
        )
        ctx = seams.stream_context_from_bundle(
            bundle,
            user_id=user_id,
            chat_id=chat_id,
            model=model,
            user_message_content=user_message_content,
            reserved_tokens=res.reserved_tokens,
            user=user,
            prior_count=prior_count,
            chat_project_id=chat.project_id,
            timing=timing,
            run_title=False,
            skip_memory_jobs=bundle.minimal_quiz,
            regenerate_backup=regenerate_backup,
        )
        await seams._top_up_reserve_for_prompt(
            res,
            settings=settings,
            ctx=ctx,
            daily_limit=seams.quota_service.daily_limit_for_user(user, settings),
        )
        try:
            async for token in seams._yield_with_chatprep_refresh(
                redis,
                res.lock_key,
                res.lock_token,
                seams.stream_and_finalize(
                    redis,
                    settings,
                    ctx,
                    should_cancel=should_cancel,
                    result=result,
                    on_status=status,
                    on_reasoning=on_reasoning,
                    resources=res,
                ),
            ):
                yield token
        except BaseException:
            if regenerate_backup is not None:
                await seams.restore_regenerate_backup(user_id, chat_id, regenerate_backup)
            raise


async def stream_edit_response(
    seams: Any,
    redis: Redis,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    message_id: UUID,
    new_content: str,
    model_alias: str | None = None,
    should_cancel: Callable[[], bool] | None = None,
    result: dict[str, Any] | None = None,
    client_timezone: str | None = None,
    client_location: str | None = None,
    client_latitude: float | None = None,
    client_longitude: float | None = None,
    on_status: StreamStatusFn | None = None,
    on_reasoning: StreamReasoningFn | None = None,
) -> AsyncIterator[str]:
    content = new_content.strip()
    if not content:
        raise ChatNotFoundError("Message cannot be empty.")
    async with seams.turn_resources(redis, user_id=user_id, chat_id=chat_id) as res:
        await seams.wait_for_pending_finalize(chat_id, redis)
        async with seams.SessionLocal() as session:
            user = await seams.users_repo.get_by_id(session, user_id)
            if user is None:
                raise ChatNotFoundError("User not found.")
            chat = await seams.chats_repo.get_by_id(session, chat_id, user_id)
            if chat is None:
                raise ChatNotFoundError("Chat not found.")
            target = await seams.messages_repo.get_by_id(session, message_id, chat_id)
            if target is None or target.role != "user":
                raise ChatNotFoundError("Only user messages can be edited.")
            model = seams.plan_service.resolve_user_model_override(
                user, model_alias, content, settings
            )
            await seams.seed_usage_from_db(redis, session, user_id)
            await res.reserve(
                user=user,
                content=content,
                model=model,
                settings=settings,
                max_output=settings.max_output_tokens,
                seed=False,
            )
            message_ids = await seams.messages_repo.ids_from_chat_at_or_after(
                session,
                chat_id,
                from_created_at=target.created_at,
                from_message_id=target.id,
            )
            summarized_count = chat.summary_message_count or 0
            if summarized_count > 0:
                total_before_edit = await seams.messages_repo.count_for_chat(session, chat_id)
                if total_before_edit - len(message_ids) < summarized_count:
                    chat.summary = None
                    chat.summary_message_count = 0
            storage_keys = await seams.attachment_lifecycle.detach_attachments_for_messages(
                session, message_ids, commit=False
            )
            await seams.messages_repo.delete_messages_from(
                session,
                chat_id,
                from_created_at=target.created_at,
                from_message_id=target.id,
            )
        async for token in seams.stream_chat_response(
            redis,
            settings,
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            model_alias=model_alias,
            should_cancel=should_cancel,
            result=result,
            client_timezone=client_timezone,
            client_location=client_location,
            client_latitude=client_latitude,
            client_longitude=client_longitude,
            on_status=on_status,
            on_reasoning=on_reasoning,
            user=user,
            skip_usage_seed=True,
            resources=res,
        ):
            yield token
        if storage_keys:
            await seams.attachment_lifecycle.delete_storage_keys(settings, storage_keys)
