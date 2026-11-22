"""What a message could ask of images, read with the chat so far: a real photo, a picture.

The words only find a candidate and write what to look up or draw (``gen_intent.py``,
``lookup_intent.py``); whether the message asks for either is the turn's read's to say,
the model that reads every chat turn (``chat.drawn_picture.read_asks``). The chat turn's
intercept (``chat/turn_intercepts.py``) and the phone's composer (``POST /images/intent``)
both ask here and then the read, so a picture the composer draws is the picture the chat
turn would draw. Word rules decided it before (owner's chat, 2026-11-22): after one painted
picture, "You keep generating an image", "did i ask about an image?" and "Man this is so
bad" each got another.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.core.db import SessionLocal
from app.modules.conversation import history as chat_history
from app.modules.images.gen_intent import (
    clean_prompt,
    is_image_gen_generate_now,
    join_subject,
    stem_subject,
    strip_polite,
)
from app.modules.images.gen_intent_second import asks_separately
from app.modules.images.gen_intent_thread import (
    extract_image_gen_prompt_from_thread,
    image_gen_revision_context,
    prior_user_contents_for_image_gen,
    revision_prompt,
)
from app.modules.images.gen_intent_words import (
    DEICTIC_SUBJECTS,
    IMAGE_NOUNS,
    VERBS_DRAW,
    VERBS_IMAGE,
)
from app.modules.images.lookup_intent import extract_image_lookup_query, is_reference_subject
from app.modules.turn_reading.see_request import asks_to_see
from app.services.text_normalize import fold_token

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.subjects.dispatch import SubjectName

_IMAGE_MARKER_ID = re.compile(
    r"\[Image: /attachments/([0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})/file\]"
)
# A change to the last generated picture is a short line ("make it blue", "now at night").
_MAX_REVISION_CHARS = 120
_MAX_ATTACHED_EDIT = 2000
_EDGE_PUNCTUATION = ".,!?;:'\"()"


@dataclass(frozen=True)
class ImageGenRequest:
    """A picture to draw. A revision edits a picture the turn starts from."""

    prompt: str
    revision: bool = False
    # The chat's last generated picture, for a revision of it.
    reference_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class PictureCandidates:
    """What a message's words could ask of images: a photo to look up, a picture to draw.
    Only candidates: the turn's read says which, if either, the message asks for."""

    lookup_query: str | None = None
    request: ImageGenRequest | None = None

    @property
    def any(self) -> bool:
        return bool(self.lookup_query) or self.request is not None

    def photo(self) -> str | None:
        """What to look up once the read asks for a photo: what the words would search for,
        else what they would draw ("a picture of Albert Einstein" is his photo)."""
        if self.lookup_query:
            return self.lookup_query
        request = self.request
        return request.prompt if request is not None and not request.revision else None

    def picture(self) -> ImageGenRequest | None:
        """What to draw once the read asks for an imagined picture: what the words would
        draw, else the subject they would search for ("show me a dragon breathing fire")."""
        if self.request is not None:
            return self.request
        query = self.lookup_query
        return ImageGenRequest(query) if query and not is_reference_subject(query) else None


@dataclass(frozen=True)
class ComposerImageIntent:
    """What the composer does with a send: look up a photo, draw a picture, or send it to chat."""

    # The maths, physics or chemistry subject that owns the text (never a picture).
    subject: SubjectName | None
    lookup_query: str | None = None
    request: ImageGenRequest | None = None


def image_reference_ids(content: str) -> list[UUID]:
    """The attachment ids of a message's ``[Image: …]`` markers, at most two."""
    return list(dict.fromkeys(UUID(value) for value in _IMAGE_MARKER_ID.findall(content)))[:2]


def _last_reply_image_ids(recent: Sequence[Any]) -> tuple[UUID, ...]:
    for row in reversed(recent):
        if getattr(row, "role", None) == "assistant":
            return tuple(image_reference_ids(getattr(row, "content", "") or ""))
    return ()


def _drawn_prompt(ids: Sequence[UUID], labels: Mapping[UUID, Any] | None) -> str | None:
    """The prompt the chat's last generated picture was drawn from, when its label is read."""
    for uid in ids:
        shown = (labels or {}).get(uid)
        label = getattr(shown, "label", None)
        if getattr(shown, "source", None) == "generated" and isinstance(label, str) and label:
            return label
    return None


# Words that name a picture, whole: a message holding one may ask for a picture the
# phrasing rules do not read ("sketch a cozy cabin in the snow", "I want an image of a fox in
# a forest, anime style"). Only a candidate: the turn's read decides, and "how do I draw a
# straight line in photoshop" is read as asking for none.
_PICTURE_WORDS = (
    IMAGE_NOUNS
    | VERBS_DRAW
    | frozenset(
        {
            "draws",
            "drew",
            "paints",
            "painting",
            "paintings",
            "sketch",
            "sketches",
            "illustrated",
            "logo",
            "poster",
            "wallpaper",
            "cartoon",
            "avatar",
            "photograph",
        }
    )
)
# Words that name nothing to draw: a picture asked for with only these ("Image", "draw
# that", "can you make me one") is a subject the chat named, for a model to read
# (``chat.referent_read``), never a prompt of its own.
_NAMES_NOTHING = (
    _PICTURE_WORDS
    | VERBS_IMAGE
    | DEICTIC_SUBJECTS
    | frozenset(
        {"a", "an", "the", "of", "me", "us", "you", "u", "i", "one", "some", "please", "pls"}
    )
    | frozenset({"just", "now", "can", "could", "would", "will", "want", "like", "give"})
)


def _words(text: str) -> list[str]:
    return [fold_token(word.strip(_EDGE_PUNCTUATION)) for word in text.split()]


def names_a_picture(text: str) -> bool:
    """Whether a word of ``text`` names a picture or drawing one (``_PICTURE_WORDS``)."""
    return any(word in _PICTURE_WORDS for word in _words(text))


def _picture_prompt(text: str) -> str | None:
    """A line naming a picture the phrasing rules did not read, as the prompt to draw if the
    read says it asks for one: its own words. None for a line naming nothing to draw, and
    for "Draw me a cat and also explain black holes", two requests whose picture is drawn
    beside the answer (``reply_picture``), never in place of it."""
    if not names_a_picture(text) or asks_separately(text):
        return None
    if all(word in _NAMES_NOTHING for word in _words(text)):
        return None
    return clean_prompt(join_subject(strip_polite(text.split())))


def _asked_picture(text: str, rows: Sequence[Any]) -> str | None:
    """The prompt of a line naming a picture the phrasing rules did not read; for a
    go-ahead ("do it"), of the user's line just before, when it named one."""
    if not is_image_gen_generate_now(text):
        return _picture_prompt(text)
    priors = prior_user_contents_for_image_gen(list(rows), text)
    return _picture_prompt(priors[-1]) if priors else None


def image_gen_request(
    text: str,
    recent: Sequence[Any],
    *,
    revisions: bool = True,
    labels: Mapping[UUID, Any] | None = None,
) -> ImageGenRequest | None:
    """The picture ``text`` would ask for, read with the chat's ``recent`` rows (oldest
    first); None when its words cannot ask for one.

    Only a candidate: the turn's read decides whether the message asks for a picture at
    all (``chat.drawn_picture.read_asks``), and these words only write what to draw. "Image"
    after "Dog" draws a dog, and "a picture of that car" the car named before. After a
    generated picture, any short line may change it ("make it blue", "now at night"): it is
    drawn again from that picture, the change added to the prompt it was drawn from
    (``labels``: the chat's pictures as ``chat.shown_pictures`` reads them). "Man this is
    so bad" is such a line too, and its read says it asks for nothing. ``revisions=False``
    (a chat with no earlier turn) skips the change reading.
    """
    rows = list(recent)
    prompt = extract_image_gen_prompt_from_thread(
        text, prior_user_contents_for_image_gen(rows, text)
    )
    if prompt:
        return ImageGenRequest(prompt)
    trimmed = text.strip()
    last_image_only, previous_subject = image_gen_revision_context(rows)
    if not (revisions and last_image_only and trimmed and len(trimmed) <= _MAX_REVISION_CHARS):
        asked = _asked_picture(text, rows)
        return ImageGenRequest(asked) if asked else None
    references = _last_reply_image_ids(rows)
    prompt = revision_prompt(text, _drawn_prompt(references, labels) or previous_subject)
    if not prompt:
        return None
    return ImageGenRequest(prompt, revision=True, reference_ids=references)


def last_reply_is_generated_image(recent: Sequence[Any]) -> bool:
    """True when the chat's newest reply is a generated picture (not a looked-up photo)."""
    last_image_only, _subject = image_gen_revision_context(list(recent))
    return last_image_only


def photo_lookup_query(text: str, recent: Sequence[Any]) -> str | None:
    """The real photo ``text`` asks for, or None.

    After a generated picture, "show it at night" edits that picture rather than
    searching for "it at night". Who "her" names otherwise is read from the chat later.
    """
    query = extract_image_lookup_query(text)
    if query and is_reference_subject(query) and last_reply_is_generated_image(recent):
        return None
    return query


def composer_candidates(
    text: str,
    recent: Sequence[Any],
    *,
    image_attached: bool = False,
    image_search: bool = True,
    chemistry_enabled: bool = True,
    can_generate: bool = True,
    labels: Mapping[UUID, Any] | None = None,
) -> ComposerImageIntent:
    """What a composer send's words could ask of images, before the read decides.

    A maths, physics or chemistry turn goes to chat. With an image attached the chat turn
    never draws, so a change to that image ("make it blue") is the composer's to draw, with
    the attachment as its reference: any line is a candidate, and the read says whether it
    asks for one ("turn this into a table" and "what's in this photo?" do not). A picture
    of "it" goes to chat too when the user can generate one: what "it" is, a model reads
    there (``chat.referent_read``), and a curve or a shape is drawn, never generated. A
    user who cannot (``can_generate``) keeps the composer's picture and its upgrade prompt.
    """
    subject = stem_subject(text, chemistry_enabled=chemistry_enabled)
    request: ImageGenRequest | None
    if not image_attached and can_generate and asks_to_see(text):
        return ComposerImageIntent(subject)
    query: str | None = None
    if image_attached:
        rows = list(recent)
        prompt = extract_image_gen_prompt_from_thread(
            text, prior_user_contents_for_image_gen(rows, text)
        )
        # Any other line may change the attached picture ("make it blue"): the read says
        # whether it does ("what's in this photo?" does not), and the line is the prompt.
        edit = None if prompt else clean_prompt(text.strip()[:_MAX_ATTACHED_EDIT])
        if prompt:
            request = ImageGenRequest(prompt)
        else:
            request = ImageGenRequest(edit, revision=True) if edit else None
    else:
        query = photo_lookup_query(text, recent) if image_search else None
        request = image_gen_request(text, recent, labels=labels)
    if subject:
        return ComposerImageIntent(subject)
    return ComposerImageIntent(subject, lookup_query=query, request=request)


def decided_intent(candidates: ComposerImageIntent, asked: str | None) -> ComposerImageIntent:
    """The send as the turn's read decides it (``asked``: ``photo``, ``image`` or None).

    A photo is looked up only when the read asks for a photo, and a picture drawn only when
    it asks for an imagined one; any other read, or none, sends the message to chat. The
    words found what to look up or draw; the read may take either for the other: "show me
    a dragon breathing fire" paints the dragon, and "a picture of Albert Einstein" looks
    up his photo.
    """
    found = PictureCandidates(candidates.lookup_query, candidates.request)
    if asked == "photo":
        return ComposerImageIntent(candidates.subject, lookup_query=found.photo())
    if asked == "image":
        return ComposerImageIntent(candidates.subject, request=found.picture())
    return ComposerImageIntent(candidates.subject)


async def composer_intent_for_chat(
    settings: Settings,
    *,
    user_id: UUID,
    text: str,
    chat_id: UUID | None,
    image_attached: bool = False,
    can_generate: bool = True,
) -> ComposerImageIntent | None:
    """A composer send over the chat's recent window, decided by the turn's read.

    The words say whether the send could ask for a picture at all (``composer_candidates``),
    so a plain message never waits; one that could is read by the model that reads every
    chat turn (``chat.picture_ask``), with the chat's last turns and what each picture
    shown in them was. None when the chat is not the user's. A draft chat with no id yet has
    no turns.
    """
    from app.modules.chat import picture_ask

    recent: list[Any] = []
    if chat_id is not None:
        async with SessionLocal() as session:
            if await chat_history.get_chat(session, chat_id, user_id) is None:
                return None
            recent = await chat_history.recent_messages(
                session, chat_id, limit=settings.recent_message_window
            )
    # The subject is the one reading behind this answer that parses with SymPy; read it in
    # the pool, and ``composer_candidates`` asks it of this request's readings.
    from app.services.subjects.dispatch import read_subject

    await read_subject(text, settings)
    labels = await picture_ask.picture_labels(user_id, recent)
    candidates = composer_candidates(
        text,
        recent,
        image_attached=image_attached,
        image_search=settings.image_search_enabled,
        chemistry_enabled=settings.chemistry_enabled,
        can_generate=can_generate,
        labels=labels,
    )
    if candidates.subject or not (candidates.lookup_query or candidates.request):
        return candidates
    asked = await picture_ask.read_picture_ask(settings, text, recent, pictures=labels)
    return decided_intent(candidates, asked)
