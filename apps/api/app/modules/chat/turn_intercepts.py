"""Turns answered without the model: a reference photo, or a generated image.

The photo lookup ("show me an ear", free and Pro) is checked before image
generation (Pro): see ``images.lookup_intent`` for why the two never compete for
the same words. Either one stores the reply itself and fills the turn's outcome.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.exceptions import ChatServiceError, QuotaExceededError
from app.models.orm import Message, User
from app.modules.attachments.markers import strip_attachment_from_content
from app.modules.chat.turn_deps import ChatTurnDeps
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import RegenerateBackup
from app.modules.images.gen_intent import stem_subject_claims
from app.modules.images.generation import ImageGenerationError
from app.modules.images.intent import (
    image_gen_request,
    last_reply_is_generated_image,
    reads_thread,
)
from app.modules.images.lookup_intent import (
    dated_lookup_query,
    extract_image_lookup_query,
    is_reference_subject,
)
from app.modules.images.search import ImageSearchError

_IMAGE_SEARCH_MODEL = "image-search-model"
_IMAGE_GEN_MODEL = "image-gen-model"


async def _replace_old_assistant(
    deps: ChatTurnDeps,
    settings: Settings,
    *,
    chat_id: UUID,
    replace_assistant_id: UUID | None,
) -> None:
    """Regenerate swaps the earlier reply only after the new one is stored."""
    if replace_assistant_id is None:
        return
    async with deps.session_factory() as session:
        old = await deps.messages.get_by_id(session, replace_assistant_id, chat_id)
        if old is not None and old.role == "assistant":
            await deps.attachments.purge_attachments_for_messages(session, settings, [old.id])
            await deps.messages.delete_message(session, old)


def _record(outcome: TurnOutcome | None, message: Message, default_model: str) -> None:
    if outcome is not None:
        outcome.message_id = str(message.id)
        outcome.final_content = message.content
        outcome.resolved_model = message.model or default_model


async def _image_gen_prompt(
    deps: ChatTurnDeps,
    *,
    chat_id: UUID,
    content: str,
    create_user_message: bool,
    skip_revision_lookup: bool,
    recent_messages: list[Any] | None,
) -> tuple[str | None, list[UUID] | None]:
    """The prompt to draw, and the earlier picture an edit starts from.

    Read by ``images.intent``, which the phone's composer asks too. History is
    read only when it can change the answer.
    """
    revisions = not skip_revision_lookup
    recent: list[Any] = []
    if reads_thread(content, revisions=revisions):
        if recent_messages is not None:
            recent = recent_messages
        else:
            async with deps.session_factory() as session:
                recent = await deps.messages.list_recent(session, chat_id, limit=20)
    request = image_gen_request(content, recent, revisions=revisions)
    if request is None:
        return None, None
    # Regenerate draws again from the references the turn was first made from.
    reference_ids = (
        list(request.reference_ids) if request.revision and create_user_message else None
    )
    return request.prompt, reference_ids


async def try_image_gen_for_turn(
    deps: ChatTurnDeps,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    content: str,
    outcome: TurnOutcome | None,
    create_user_message: bool,
    replace_assistant_id: UUID | None = None,
    skip_revision_lookup: bool = False,
    recent_messages: list[Any] | None = None,
) -> bool:
    if not deps.plan.can_use(user, "image_generation", settings):
        return False
    if stem_subject_claims(content, chemistry_enabled=settings.chemistry_enabled):
        return False
    image_prompt, reference_ids = await _image_gen_prompt(
        deps,
        chat_id=chat_id,
        content=content,
        create_user_message=create_user_message,
        skip_revision_lookup=skip_revision_lookup,
        recent_messages=recent_messages,
    )
    if not image_prompt:
        return False
    try:
        _user_msg, asst_msg = await deps.image_generation.generate_for_chat(
            settings,
            user=user,
            chat_id=chat_id,
            prompt=image_prompt,
            user_message_content=(content.strip() if create_user_message else None),
            create_user_message=create_user_message,
            reference_attachment_ids=reference_ids,
        )
    except ImageGenerationError as exc:
        if exc.status_code == 429:
            raise QuotaExceededError(exc.detail) from exc
        if exc.status_code in (403, 404):
            return False
        raise ChatServiceError(exc.detail) from exc

    await _replace_old_assistant(
        deps, settings, chat_id=chat_id, replace_assistant_id=replace_assistant_id
    )
    _record(outcome, asst_msg, _IMAGE_GEN_MODEL)
    return True


async def _photo_subject_from_chat(
    deps: ChatTurnDeps,
    settings: Settings,
    *,
    chat_id: UUID,
    content: str,
    recent_messages: list[Any] | None,
    replace_assistant_id: UUID | None,
) -> str | None:
    """Who "her" / "it" is in "show me her image", read from the chat; None if unclear.

    After a generated picture, "show it at night" edits that picture: the
    image-generation intercept owns it, so this returns None.
    """
    if recent_messages is not None:
        recent = recent_messages
    else:
        async with deps.session_factory() as session:
            recent = await deps.messages.list_recent(
                session, chat_id, limit=settings.recent_message_window
            )
    if replace_assistant_id is not None:
        recent = [row for row in recent if getattr(row, "id", None) != replace_assistant_id]
    if last_reply_is_generated_image(recent):
        return None
    return await deps.references.resolve_reference(
        settings,
        kind="photo",
        request=content,
        turns=deps.references.turns_from_rows(recent),
    )


async def try_image_lookup_for_turn(
    deps: ChatTurnDeps,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    content: str,
    outcome: TurnOutcome | None,
    create_user_message: bool,
    replace_assistant_id: UUID | None = None,
    recent_messages: list[Any] | None = None,
) -> bool:
    """Deterministic reference-photo lookup intercept ("show me an ear").

    Failures that aren't quota-related fall through to a normal model answer
    instead of erroring the turn (a missing photo is not worth breaking chat).
    """
    if not settings.image_search_enabled:
        return False
    query = extract_image_lookup_query(content)
    if not query:
        return False
    if is_reference_subject(query):
        query = await _photo_subject_from_chat(
            deps,
            settings,
            chat_id=chat_id,
            content=content,
            recent_messages=recent_messages,
            replace_assistant_id=replace_assistant_id,
        )
        if not query:
            return False
    query = dated_lookup_query(query, datetime.now(UTC).year)
    try:
        _user_msg, asst_msg = await deps.image_search.search_and_attach_for_chat(
            settings,
            user=user,
            chat_id=chat_id,
            query=query,
            user_message_content=(content.strip() if create_user_message else None),
            create_user_message=create_user_message,
        )
    except ImageSearchError as exc:
        if exc.status_code == 429:
            raise QuotaExceededError(exc.detail) from exc
        if exc.status_code in (404, 502, 503):
            return False
        raise ChatServiceError(exc.detail) from exc

    await _replace_old_assistant(
        deps, settings, chat_id=chat_id, replace_assistant_id=replace_assistant_id
    )
    _record(outcome, asst_msg, _IMAGE_SEARCH_MODEL)
    return True


async def intercept_new_turn(
    deps: ChatTurnDeps,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    content: str,
    outcome: TurnOutcome | None,
    recent_messages: list[Any],
    prior_count: int,
) -> bool:
    """A new message answered by a photo or a picture; True when one stored the reply."""
    if await try_image_lookup_for_turn(
        deps,
        settings,
        user=user,
        chat_id=chat_id,
        content=content,
        outcome=outcome,
        create_user_message=True,
        recent_messages=recent_messages,
    ):
        return True
    return await try_image_gen_for_turn(
        deps,
        settings,
        user=user,
        chat_id=chat_id,
        content=content,
        outcome=outcome,
        create_user_message=True,
        skip_revision_lookup=prior_count == 0,
        recent_messages=recent_messages,
    )


def _image_regenerate_content(
    deps: ChatTurnDeps, content: str, backup: RegenerateBackup | None
) -> str:
    """Regenerate the recorded input, not the latest generated output.

    Edit wording need not contain "image" or satisfy short-revision heuristics.
    The persisted assistant model establishes intent.
    """
    if backup is None or backup.model != _IMAGE_GEN_MODEL:
        return content
    for ref_id in deps.image_generation.image_reference_ids(content):
        content = strip_attachment_from_content(content, ref_id)
    return f"Generate image: {content}"


async def intercept_regenerate(
    deps: ChatTurnDeps,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    content: str,
    backup: RegenerateBackup | None,
    outcome: TurnOutcome | None,
) -> bool:
    """Regenerating a photo or a picture makes another; True when one replaced the reply."""
    replace_id = backup.message_id if backup is not None else None
    if backup is not None and backup.model == _IMAGE_SEARCH_MODEL:
        if await try_image_lookup_for_turn(
            deps,
            settings,
            user=user,
            chat_id=chat_id,
            content=content,
            outcome=outcome,
            create_user_message=False,
            replace_assistant_id=replace_id,
        ):
            return True
    return await try_image_gen_for_turn(
        deps,
        settings,
        user=user,
        chat_id=chat_id,
        content=_image_regenerate_content(deps, content, backup),
        outcome=outcome,
        create_user_message=False,
        replace_assistant_id=replace_id,
    )
