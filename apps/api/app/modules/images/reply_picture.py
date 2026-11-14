"""A picture drawn above an answer, for a message that asks for one among other things.

"Draw a cat wearing a hat and also explain what a black hole is" used to get
nothing: the intercept that draws a picture takes a whole turn and declined the
compound line, so neither the picture nor the explanation came back clearly. Now
the picture is drawn while the model answers the rest, and the finished reply
carries both: the picture above the text, or one line saying why it could not, in
the app's language (``reply_picture_lines``).

Drawing is generation's own: the same plan check, daily slot, storage and spend
cap (``generation``); only the rows differ. The picture is stored unlinked and the
reply links it when it saves, as a looked-up answer photo is (``answer_photo``).
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.orm import User
from app.modules.attachments import service as attachments_service
from app.modules.attachments.markers import image_marker
from app.modules.billing import is_paid
from app.modules.images import generation
from app.modules.images.reply_picture_lines import Reason, not_drawn_line, reason_for_code
from app.modules.images.written_bytes import WrittenBytes
from app.services import quota as quota_service

logger = logging.getLogger(__name__)

# A picture takes 10-40 s; the answer usually streams in less. The provider's own
# limit (120 s) is longer, so a reply never waits on a stuck call past this.
_WAIT_SECONDS = 90.0


async def draw_unlinked(settings: Settings, *, user: User, chat_id: UUID, prompt: str) -> UUID:
    """Draw one picture and store it unlinked, under ``generate_for_chat``'s rules.

    Raises ``ImageGenerationError`` as generation does; the slot is given back on a
    failure before the provider is asked, and kept after (``generation._ReservedQuota``);
    the bytes written are deleted either way.
    """
    cleaned = prompt.strip()
    gateway, _references, redis = await generation._authorize_generation(
        settings,
        user=user,
        chat_id=chat_id,
        create_user_message=True,
        reference_attachment_ids=[],
    )
    written = WrittenBytes(gateway)
    async with generation._ReservedQuota(redis, user, settings, undo=written.delete_all) as slot:
        stored = await generation._generate_and_store(
            settings,
            written,
            user_id=user.id,
            prompt=cleaned,
            aspect_ratio=None,
            references=[],
            copy_references=False,
            on_provider_call=slot.spend,
        )
        async with SessionLocal() as session:
            await attachments_service.add_server_images(
                session,
                user_id=user.id,
                images=[stored.image],
                source="generated",
                label=cleaned,
            )
            await session.commit()
    try:
        await quota_service.record_global_spend(redis, quota_service.IMAGE_GEN_SPEND_USD)
    except Exception:
        logger.exception("record_global_spend failed after a reply picture")
    return stored.image.attachment_id


class ReplyPicture:
    """One picture for one reply: started with the turn, attached when the reply ends.

    ``figure`` answers whether the turn's read calls the picture a maths figure ("draw the
    cylinder and find its volume"): maths draws that from the question's values, so no
    painting is made (nor a day's picture spent) and no line says one was not."""

    def __init__(
        self,
        subject: str,
        *,
        task: asyncio.Task[UUID | None] | None,
        refusal: Reason | None = None,
        locale: str | None = None,
        paid: bool = False,
        figure: asyncio.Task[bool] | None = None,
    ) -> None:
        self.subject = subject
        self._task = task
        self._refusal = refusal
        self._locale = locale
        self._paid = paid
        self._figure = figure

    @classmethod
    def start(
        cls,
        settings: Settings,
        *,
        user: User,
        chat_id: UUID,
        prompt: str,
        language: str | None = None,
        figure: asyncio.Task[bool] | None = None,
    ) -> ReplyPicture:
        """Start drawing once the read says it is no maths figure; a line saying why not is
        in ``language`` (else the app's)."""

        async def drawn() -> UUID | None:
            if figure is not None and await asyncio.shield(figure):
                return None  # a maths figure: maths draws it
            return await draw_unlinked(settings, user=user, chat_id=chat_id, prompt=prompt)

        task = asyncio.create_task(drawn(), name="reply_picture")
        locale = language or user.locale
        return cls(prompt, task=task, locale=locale, paid=is_paid(user), figure=figure)

    @classmethod
    def refused(
        cls, subject: str, code: str, locale: str | None, figure: asyncio.Task[bool] | None = None
    ) -> ReplyPicture:
        """The picture cannot be drawn (the plan, drawing off): one line, by generation's code."""
        return cls(subject, task=None, refusal=reason_for_code(code), locale=locale, figure=figure)

    async def _is_figure(self) -> bool:
        if self._figure is None or self._figure.cancelled():
            return False
        try:
            return await asyncio.wait_for(asyncio.shield(self._figure), timeout=_WAIT_SECONDS)
        except Exception:
            # No answer from the read is no figure: the picture is drawn as asked.
            logger.info("reply picture's figure read failed", exc_info=True)
            return False

    async def attach(self, text: str) -> tuple[str, list[UUID]]:
        """The reply with the picture above it, and its id; or the reply and why not."""
        if await self._is_figure():
            return text, []
        if self._task is None:
            return self._with_note(text, self._refusal or "failed"), []
        try:
            picture = await asyncio.wait_for(asyncio.shield(self._task), timeout=_WAIT_SECONDS)
        except TimeoutError:
            # A picture finished after the reply saved stays unlinked; the reaper removes it.
            logger.info("Reply picture took too long; the reply goes without it")
            return self._with_note(text, "too_slow"), []
        except generation.ImageGenerationError as exc:
            # By its code: the refusal's English (or a provider's words) never goes in.
            return self._with_note(text, reason_for_code(exc.code)), []
        except Exception:
            logger.exception("Reply picture failed")
            return self._with_note(text, "failed"), []
        if picture is None:
            return text, []
        return f"{image_marker(picture)}\n\n{text.lstrip()}", [picture]

    def _with_note(self, text: str, reason: Reason) -> str:
        line = not_drawn_line(reason, self.subject, self._locale, paid=self._paid)
        return f"{text.rstrip()}\n\n{line}".strip()

    def cancel(self) -> None:
        """A stopped reply draws nothing: cancelling gives the day's slot back."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
        if self._figure is not None and not self._figure.done():
            self._figure.cancel()
