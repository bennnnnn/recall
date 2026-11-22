"""Turns answered without the model: a reference photo, or a generated image.

The words find what a message could ask of images (``images.intent``); the turn's read
decides whether it asks for a photo, a painted picture or neither
(``drawn_picture.read_asks``). Either one stores the reply itself and fills the turn's
outcome; a read with no answer leaves the turn to the reply.
"""

import asyncio
import functools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.exceptions import ChatServiceError, SpendCapReachedError, TurnRefusedError
from app.models.orm import Message, User
from app.modules.attachments.markers import strip_attachment_from_content
from app.modules.chat.drawn_picture import read_paints_none, read_picture
from app.modules.chat.referent_read import Referent, referent_for_turn
from app.modules.chat.reply_language import line_language
from app.modules.chat.shown_pictures import ShownPictures, labels_for_turn
from app.modules.chat.stream_status import StreamStatusFn, StreamStatusPhase, clip_status_detail
from app.modules.chat.turn_decision import TurnDecision, drop_read
from app.modules.chat.turn_deps import ChatTurnDeps
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import RegenerateBackup
from app.modules.chat.turn_prep.clauses import request_body
from app.modules.chat.turn_trace import emit_turn_trace
from app.modules.images.gen_intent import extract_image_gen_prompt, stem_subject_claims
from app.modules.images.generation import ImageGenerationError
from app.modules.images.intent import (
    ImageGenRequest,
    PictureCandidates,
    image_gen_request,
    last_reply_is_generated_image,
)
from app.modules.images.lookup_intent import (
    dated_lookup_query,
    extract_image_lookup_query,
    is_reference_subject,
    names_a_drawing,
)
from app.modules.images.reply_picture import ReplyPicture
from app.modules.images.schemas import PHOTO_LOOKUP_MODEL as _IMAGE_SEARCH_MODEL
from app.modules.images.search import ImageSearchError
from app.services.solving import VerifiedSolveBlock
from app.services.subjects.dispatch import asks_a_subject_to_show, subject_shows_it

_IMAGE_GEN_MODEL = "image-gen-model"
_READ_GRACE = 0.5


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


async def _starting(
    outcome: TurnOutcome | None,
    on_status: StreamStatusFn | None,
    phase: StreamStatusPhase,
    detail: str,
) -> None:
    """A photo or a picture is under way. Stop cuts it off as it did (the user's row
    comes with its reply), and its label goes up as the tool loop's does: the typing
    dots alone sat there for the seconds it takes."""
    if outcome is not None:
        outcome.mark_stop_safe()
    if on_status is not None:
        await on_status(phase, clip_status_detail(detail))


def _record(outcome: TurnOutcome | None, message: Message, default_model: str) -> None:
    """A photo or a picture is the turn's reply: the turn ends here, and its trace too."""
    if outcome is not None:
        outcome.message_id = str(message.id)
        outcome.final_content = message.content
        outcome.resolved_model = message.model or default_model
    emit_turn_trace(None, outcome=outcome, path="intercept")


def _gen_request(
    deps: ChatTurnDeps,
    settings: Settings,
    *,
    user: User,
    content: str,
    recent: list[Any],
    revisions: bool,
    pictures: ShownPictures,
) -> ImageGenRequest | None:
    """The picture the words could ask for, when this user may have one drawn: what to
    draw if the read says the message asks for a picture. A maths, physics or chemistry
    turn is never painted."""
    if not settings.image_generation_enabled or not deps.plan.can_use(
        user, "image_generation", settings
    ):
        return None
    request = image_gen_request(content, recent, revisions=revisions, labels=pictures)
    if request is None or stem_subject_claims(
        content, chemistry_enabled=settings.chemistry_enabled
    ):
        return None
    return request


async def try_image_gen_for_turn(
    deps: ChatTurnDeps,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    content: str,
    request: ImageGenRequest,
    outcome: TurnOutcome | None,
    create_user_message: bool,
    replace_assistant_id: UUID | None = None,
    on_status: StreamStatusFn | None = None,
) -> bool:
    """Draw the picture the read said the message asks for; True when it stored the reply.
    A regenerate draws again from the references the turn was first made from."""
    reference_ids = (
        list(request.reference_ids) if request.revision and create_user_message else None
    )
    await _starting(outcome, on_status, "image_gen", request.prompt)
    try:
        _user_msg, asst_msg = await deps.image_generation.generate_for_chat(
            settings,
            user=user,
            chat_id=chat_id,
            prompt=request.prompt,
            user_message_content=(content.strip() if create_user_message else None),
            create_user_message=create_user_message,
            reference_attachment_ids=reference_ids,
        )
    except ImageGenerationError as exc:
        if exc.code == "spend_cap":
            # The picture's own line on the phone, not "new messages are paused for everyone".
            raise SpendCapReachedError(exc.message, feature="image_generation") from exc
        if exc.status_code in (403, 404):
            return False
        if exc.code in ("daily_limit", "content_blocked"):
            # The picture's own limit or the provider's refusal: said as such, not as
            # the user's chat quota being spent.
            raise TurnRefusedError(exc.message, code=exc.code, feature="image_generation") from exc
        raise ChatServiceError(exc.detail) from exc

    await _replace_old_assistant(
        deps, settings, chat_id=chat_id, replace_assistant_id=replace_assistant_id
    )
    _record(outcome, asst_msg, _IMAGE_GEN_MODEL)
    return True


async def _recent_rows(
    deps: ChatTurnDeps,
    settings: Settings,
    *,
    chat_id: UUID,
    recent_messages: list[Any] | None,
    replace_assistant_id: UUID | None,
) -> list[Any]:
    if recent_messages is not None:
        recent = recent_messages
    else:
        async with deps.session_factory() as session:
            recent = await deps.messages.list_recent(
                session, chat_id, limit=settings.recent_message_window
            )
    if replace_assistant_id is not None:
        recent = [row for row in recent if getattr(row, "id", None) != replace_assistant_id]
    return list(recent)


async def _photo_subject_from_chat(
    deps: ChatTurnDeps, settings: Settings, *, content: str, recent: list[Any]
) -> str | None:
    """Who "her" / "it" is in "show me her image", read from the chat; None if unclear.

    After a generated picture, "show it at night" changes that picture: it is the
    painting's to answer, so this returns None.
    """
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
    query: str,
    outcome: TurnOutcome | None,
    create_user_message: bool,
    recent: list[Any],
    replace_assistant_id: UUID | None = None,
    misses: set[str] | None = None,
    on_status: StreamStatusFn | None = None,
) -> bool:
    """Look up the photo the read said the message asks for ("show me an ear"); True when
    it stored the reply. ``query`` is what the words found to search for.

    Failures that aren't quota-related fall through to a normal model answer
    instead of erroring the turn (a missing photo is not worth breaking chat).
    A search that ran and found no photo adds "photo" to ``misses``, so the
    turn's tool loop does not search again.
    """
    if is_reference_subject(query):
        found = await _photo_subject_from_chat(deps, settings, content=content, recent=recent)
        if not found:
            # Who "her" is, unclear: the reply's model reads the chat, and may search.
            return False
        if names_a_drawing(found):
            # "Water and carbon dioxide molecules": drawn by the app, so the tool loop
            # offers no photo search either.
            _missed(misses, "photo")
            return False
        query = found
    query = dated_lookup_query(query, datetime.now(UTC).year)
    await _starting(outcome, on_status, "finding_photo", query)
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
        # At the photo cap (or the spend cap) the turn is answered in words instead.
        if exc.status_code in (404, 429, 502, 503):
            _missed(misses, "photo")
            return False
        raise ChatServiceError(exc.detail) from exc

    await _replace_old_assistant(
        deps, settings, chat_id=chat_id, replace_assistant_id=replace_assistant_id
    )
    _record(outcome, asst_msg, _IMAGE_SEARCH_MODEL)
    return True


def _missed(misses: set[str] | None, *kinds: str) -> None:
    if misses is not None:
        misses.update(kinds)


@dataclass(frozen=True)
class _PictureTurn:
    """One turn's picture ask: its words, the chat before it, and where it saves."""

    user: User
    chat_id: UUID
    content: str
    recent: list[Any]
    outcome: TurnOutcome | None
    create_user_message: bool
    replace_assistant_id: UUID | None = None


async def _answer_by_read(
    deps: ChatTurnDeps,
    settings: Settings,
    turn: _PictureTurn,
    *,
    candidates: PictureCandidates,
    read: asyncio.Future[TurnDecision | None] | None,
    misses: set[str] | None,
    on_status: StreamStatusFn | None,
) -> bool:
    """The photo or the picture the turn's read says the message asks for, if the words
    found one (``candidates``); True when one stored the reply. Neither when the read says
    neither, or has no answer: the reply answers in words, and its tool loop offers neither
    tool (``misses``)."""
    if not candidates.any:
        return False
    # The read began with the turn and ends by its own budget; a stuck one is no answer.
    asked = await read_picture(read, settings.live_read_timeout_seconds + _READ_GRACE)
    query = candidates.photo() if asked == "photo" and settings.image_search_enabled else None
    request = candidates.picture() if asked == "image" else None
    if query:
        handled = await try_image_lookup_for_turn(
            deps,
            settings,
            user=turn.user,
            chat_id=turn.chat_id,
            content=turn.content,
            query=query,
            outcome=turn.outcome,
            create_user_message=turn.create_user_message,
            recent=turn.recent,
            replace_assistant_id=turn.replace_assistant_id,
            misses=misses,
            on_status=on_status,
        )
    elif request is not None:
        handled = await try_image_gen_for_turn(
            deps,
            settings,
            user=turn.user,
            chat_id=turn.chat_id,
            content=turn.content,
            request=request,
            outcome=turn.outcome,
            create_user_message=turn.create_user_message,
            replace_assistant_id=turn.replace_assistant_id,
            on_status=on_status,
        )
    else:
        handled = False
    if not handled:
        # Neither tool for what the read did not ask; and a photo asked for and none found
        # is answered in words: a painting would pass for a photo ("show me a picture of
        # Albert Einstein" drew a real person).
        _missed(misses, *(kind for kind in ("photo", "image") if kind != asked))
    return handled


def reply_picture_prompt(content: str, settings: Settings) -> str | None:
    """What to draw for the picture part of a multi-part message, if it has one."""
    from app.modules.chat.turn_prep.reading import plan_of

    plan = plan_of(content, settings)
    asked = plan.of_kind("image") if plan.multi else ()
    return extract_image_gen_prompt(request_body(asked[0].text)) if asked else None


def start_reply_picture(
    deps: ChatTurnDeps,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    content: str,
    read: asyncio.Future[TurnDecision | None] | None = None,
    verified: VerifiedSolveBlock | None = None,
) -> ReplyPicture | None:
    """The picture one part of a multi-part message asks for, drawn beside the answer.

    "Draw a cat wearing a hat and also explain what a black hole is": the intercept
    above declines the whole line, so the model answers the rest while this draws. "Draw
    the cylinder and find its volume" is a maths figure when the turn's read says so, and
    "find the current and draw the circuit" physics' schematic when its solve (``verified``)
    drew it: the app draws it (``drawn_picture.app_draws``), and no painting (nor a line
    saying none came) goes with the reply.
    """
    prompt = reply_picture_prompt(content, settings)
    if not prompt:
        return None
    # No painting unless the read says the message asks for one, and the app does not
    # draw the picture itself: the words only found the picture part.
    figure = asyncio.ensure_future(read_paints_none(read, verified))
    # The line saying why not is in the reply's language, which follows the message. The
    # picture part is only recognised in English ("draw …"), so a message no language
    # plainly claims gets an English reply, and an English line under it.
    language = line_language(content, "en")
    if not settings.image_generation_enabled:
        return ReplyPicture.refused(prompt, "not_available", language, figure)
    if not deps.plan.can_use(user, "image_generation", settings):
        return ReplyPicture.refused(prompt, "not_in_plan", language, figure)
    return ReplyPicture.start(
        settings, user=user, chat_id=chat_id, prompt=prompt, language=language, figure=figure
    )


def _ends_the_read[**P](fn: Callable[P, Awaitable[bool]]) -> Callable[P, Awaitable[bool]]:
    """An intercept that answered the turn (True) stops its read: it has used what it needed
    of it, and no reply call will ask (MODEL-06). Its two or three calls were billed on to
    their own timeout."""

    @functools.wraps(fn)
    async def intercept(*args: P.args, **kwargs: P.kwargs) -> bool:
        handled = await fn(*args, **kwargs)
        read = kwargs.get("read")
        if handled and isinstance(read, asyncio.Task):
            drop_read(read)
        return handled

    return intercept


@_ends_the_read
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
    misses: set[str] | None = None,
    on_status: StreamStatusFn | None = None,
    read: asyncio.Future[TurnDecision | None] | None = None,
) -> bool:
    """A new message answered by a photo or a picture; True when one stored the reply.

    The words say whether it could ask for one (a plain message never waits for the read
    here); the turn's read says whether it does (``drawn_picture.read_asks``). A lookup that
    ran and found nothing, and a picture the read did not ask for, are added to ``misses``.
    "Show it" is read first: what a model reads as "it" (``referent_read``) may be a
    subject's to draw.
    """
    referent = await referent_for_turn(settings, content, recent_messages)
    if await subject_shows_it(settings, content, recent_messages, _problem(referent)):
        # Shown by a subject (its graph, figure, scene or molecules): no photo, no generated
        # picture, no photo tool.
        _missed(misses, "photo")
        return False
    pictures = await labels_for_turn()
    candidates = PictureCandidates(
        lookup_query=_lookup_words(settings, content),
        request=_gen_request(
            deps,
            settings,
            user=user,
            content=content,
            recent=recent_messages,
            revisions=prior_count > 0,
            pictures=pictures,
        ),
    )
    turn = _PictureTurn(
        user=user,
        chat_id=chat_id,
        content=content,
        recent=recent_messages,
        outcome=outcome,
        create_user_message=True,
    )
    return await _answer_by_read(
        deps,
        settings,
        turn,
        candidates=candidates,
        read=read,
        misses=misses,
        on_status=on_status,
    )


def _lookup_words(settings: Settings, content: str) -> str | None:
    return extract_image_lookup_query(content) if settings.image_search_enabled else None


def _problem(referent: Referent | None) -> str | None:
    return None if referent is None else referent.problem


def _image_regenerate_content(
    deps: ChatTurnDeps, content: str, backup: RegenerateBackup | None
) -> str:
    """Regenerate the recorded input, not the latest generated output.

    Its words need not name a picture ("make it blue"); the persisted assistant model
    says what to draw again, and the turn's read whether the line asked for a picture.
    """
    if backup is None or backup.model != _IMAGE_GEN_MODEL:
        return content
    for ref_id in deps.image_generation.image_reference_ids(content):
        content = strip_attachment_from_content(content, ref_id)
    return f"Generate image: {content}"


@_ends_the_read
async def intercept_regenerate(
    deps: ChatTurnDeps,
    settings: Settings,
    *,
    user: User,
    chat_id: UUID,
    content: str,
    backup: RegenerateBackup | None,
    outcome: TurnOutcome | None,
    misses: set[str] | None = None,
    on_status: StreamStatusFn | None = None,
    read: asyncio.Future[TurnDecision | None] | None = None,
    recent_messages: list[Any] | None = None,
) -> bool:
    """Regenerating a photo or a picture makes another when the turn's read says the line
    asks for one; True when one replaced the reply. "Man this is so bad" painted by mistake
    is answered in words when regenerated. ``recent_messages``: the chat before the line,
    as the turn loaded it (else read here).

    A lookup that ran and found nothing is added to ``misses`` ("photo").
    """
    replace_id = backup.message_id if backup is not None else None
    recent = await _recent_rows(
        deps,
        settings,
        chat_id=chat_id,
        recent_messages=recent_messages,
        replace_assistant_id=replace_id,
    )
    if asks_a_subject_to_show(content):
        referent = await referent_for_turn(settings, content, recent)
        if await subject_shows_it(settings, content, recent, _problem(referent)):
            _missed(misses, "photo")
            return False
    photo_backup = backup is not None and backup.model == _IMAGE_SEARCH_MODEL
    candidates = PictureCandidates(
        lookup_query=_lookup_words(settings, content) if photo_backup else None,
        request=_gen_request(
            deps,
            settings,
            user=user,
            content=_image_regenerate_content(deps, content, backup),
            recent=recent,
            revisions=True,
            pictures=await labels_for_turn(),
        ),
    )
    turn = _PictureTurn(
        user=user,
        chat_id=chat_id,
        content=content,
        recent=recent,
        outcome=outcome,
        create_user_message=False,
        replace_assistant_id=replace_id,
    )
    return await _answer_by_read(
        deps,
        settings,
        turn,
        candidates=candidates,
        read=read,
        misses=misses,
        on_status=on_status,
    )
