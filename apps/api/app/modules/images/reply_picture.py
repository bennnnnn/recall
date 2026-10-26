# ruff: noqa: RUF001 - the line is written in the app's languages (Turkish dotless i, Cyrillic)
"""A picture drawn above an answer, for a message that asks for one among other things.

"Draw a cat wearing a hat and also explain what a black hole is" used to get
nothing: the intercept that draws a picture takes a whole turn and declined the
compound line, so neither the picture nor the explanation came back clearly. Now
the picture is drawn while the model answers the rest, and the finished reply
carries both: the picture above the text, or one line saying why it could not.

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
from app.core.validation import normalize_locale_code
from app.models.orm import User
from app.modules.attachments import service as attachments_service
from app.modules.attachments.markers import image_marker
from app.modules.images import generation
from app.services import quota as quota_service

logger = logging.getLogger(__name__)

# A picture takes 10-40 s; the answer usually streams in less. The provider's own
# limit (120 s) is longer, so a reply never waits on a stuck call past this.
_WAIT_SECONDS = 90.0
_NOT_MADE = "I couldn't draw the picture ({subject}) this time: {reason}"
_TOO_SLOW = "the picture took too long. Ask for it again on its own."
_FAILED = "something went wrong. Ask for it again on its own."
# The day's spend cap (``generation``'s ``spend_cap``, or drawing switched off): the whole
# line in the app's language, as the To-do line is (``todos.chat_language``). Its English
# showed under a reply in any language.
_PAUSED = {
    "en": "I couldn't draw the picture ({subject}) this time: "
    "Image generation is temporarily unavailable. Try again later.",
    "es": "Esta vez no pude dibujar la imagen ({subject}): "
    "la generación de imágenes no está disponible temporalmente. Inténtalo más tarde.",
    "fr": "Je n'ai pas pu dessiner l'image ({subject}) cette fois : "
    "la génération d'images est temporairement indisponible. Réessayez plus tard.",
    "de": "Das Bild ({subject}) konnte ich diesmal nicht zeichnen: "
    "Die Bilderstellung ist vorübergehend nicht verfügbar. Versuche es später erneut.",
    "it": "Questa volta non sono riuscito a disegnare l'immagine ({subject}): "
    "la generazione di immagini non è temporaneamente disponibile. Riprova più tardi.",
    "pt": "Desta vez não consegui desenhar a imagem ({subject}): "
    "a geração de imagens está temporariamente indisponível. Tente novamente mais tarde.",
    "tr": "Bu sefer resmi ({subject}) çizemedim: "
    "görsel oluşturma geçici olarak kullanılamıyor. Daha sonra tekrar deneyin.",
    "ru": "В этот раз не удалось нарисовать картинку ({subject}): "
    "создание изображений временно недоступно. Попробуйте позже.",
    "am": "ምስሉን ({subject}) በዚህ ጊዜ መሳል አልቻልኩም፦ ምስል መፍጠር ለጊዜው አይገኝም። ቆይተው እንደገና ይሞክሩ።",
}


def paused_note(subject: str, locale: str | None) -> str:
    """The line for a picture the spend cap stopped, in ``locale`` (English otherwise)."""
    line = _PAUSED.get(normalize_locale_code(locale), _PAUSED["en"])
    return line.format(subject=subject)


async def draw_unlinked(settings: Settings, *, user: User, chat_id: UUID, prompt: str) -> UUID:
    """Draw one picture and store it unlinked, under ``generate_for_chat``'s rules.

    Raises ``ImageGenerationError`` as generation does; the slot is given back on
    any failure (``generation._ReservedQuota``), and the bytes written are deleted.
    """
    cleaned = prompt.strip()
    gateway, _references, redis = await generation._authorize_generation(
        settings,
        user=user,
        chat_id=chat_id,
        create_user_message=True,
        reference_attachment_ids=[],
    )
    written = generation._WrittenBytes(gateway)
    async with generation._ReservedQuota(redis, user, settings, undo=written.delete_all):
        stored = await generation._generate_and_store(
            settings,
            written,
            user_id=user.id,
            prompt=cleaned,
            aspect_ratio=None,
            references=[],
            copy_references=False,
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
    """One picture for one reply: started with the turn, attached when the reply ends."""

    def __init__(
        self,
        subject: str,
        *,
        task: asyncio.Task[UUID] | None,
        refusal: str = "",
        locale: str | None = None,
        paused: bool = False,
    ) -> None:
        self.subject = subject
        self._task = task
        self._refusal = refusal
        self._locale = locale
        self._paused = paused

    @classmethod
    def start(cls, settings: Settings, *, user: User, chat_id: UUID, prompt: str) -> ReplyPicture:
        task = asyncio.create_task(
            draw_unlinked(settings, user=user, chat_id=chat_id, prompt=prompt),
            name="reply_picture",
        )
        return cls(prompt, task=task, locale=user.locale)

    @classmethod
    def refused(cls, subject: str, reason: str) -> ReplyPicture:
        """The picture cannot be drawn (the plan): the reply says so in one line."""
        return cls(subject, task=None, refusal=reason)

    @classmethod
    def paused_for(cls, subject: str, locale: str | None) -> ReplyPicture:
        """Drawing is switched off: the spend cap's line, in the app's language."""
        return cls(subject, task=None, locale=locale, paused=True)

    async def attach(self, text: str) -> tuple[str, list[UUID]]:
        """The reply with the picture above it, and its id; or the reply and why not."""
        if self._task is None:
            if self._paused:
                return self._with_line(text, paused_note(self.subject, self._locale)), []
            return self._with_note(text, self._refusal), []
        try:
            picture = await asyncio.wait_for(asyncio.shield(self._task), timeout=_WAIT_SECONDS)
        except TimeoutError:
            # A picture finished after the reply saved stays unlinked; the reaper removes it.
            logger.info("Reply picture took too long; the reply goes without it")
            return self._with_note(text, _TOO_SLOW), []
        except generation.ImageGenerationError as exc:
            if exc.code == "spend_cap":
                return self._with_line(text, paused_note(self.subject, self._locale)), []
            return self._with_note(text, exc.detail), []
        except Exception:
            logger.exception("Reply picture failed")
            return self._with_note(text, _FAILED), []
        return f"{image_marker(picture)}\n\n{text.lstrip()}", [picture]

    def _with_note(self, text: str, reason: str) -> str:
        return self._with_line(
            text, _NOT_MADE.format(subject=self.subject, reason=reason.rstrip(".") + ".")
        )

    @staticmethod
    def _with_line(text: str, line: str) -> str:
        return f"{text.rstrip()}\n\n{line}".strip()

    def cancel(self) -> None:
        """A stopped reply draws nothing: cancelling gives the day's slot back."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
