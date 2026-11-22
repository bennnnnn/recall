"""What an earlier picture in the chat was, as the models that read the chat see it.

A generated picture or a looked-up photo is stored as its reply's ``[Image: /attachments/…]``
line. Read back as history, that line told the reply's model nothing: after a picture the
app drew for "No you displayed an image", it answered "I can't see any image… I've been
sending stray image markers" (owner's chat, 2026-11-22), and the turn's read could not tell
that a picture had been shown at all. Each such line is now said in words: who showed it
(the app, not the model), whether it was generated or found, and what it showed, the
prompt it drew or the photo searched for (kept as the attachment's label,
``attachments.service.add_server_images``).

The labels are read once a turn, beside the turn's read (``start_labels``), from the rows
the turn loaded; nothing here raises, and a label it cannot read leaves the line said by
the reply's model name alone.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.readings import keep_for_turn, kept_for_turn
from app.modules.attachments.markers import image_attachment_ids_from_text

logger = logging.getLogger(__name__)

# The reply rows' model for a generated picture and a looked-up photo
# (``images.generation``, ``images.schemas.PHOTO_LOOKUP_MODEL``).
_GENERATED_MODEL = "image-gen-model"
_PHOTO_MODEL = "image-search-model"
_KEPT = "shown_pictures"
# Labels are a hint: a slow read leaves the lines said by the row's model.
_LOAD_SECONDS = 1.0
_MAX_IDS = 20
_LABEL_CHARS = 200


@dataclass(frozen=True)
class ShownPicture:
    """A picture's attachment row: ``generated``, ``search`` or ``upload``, and its label."""

    source: str
    label: str | None = None


ShownPictures = Mapping[UUID, ShownPicture]


def _marker_ids(content: str) -> list[UUID]:
    return image_attachment_ids_from_text(content) if "[Image:" in content else []


def picture_ids(rows: Iterable[Any]) -> list[UUID]:
    """The pictures the assistant's rows show, newest last, at most ``_MAX_IDS``."""
    ids: list[UUID] = []
    for row in rows:
        content = getattr(row, "content", None)
        if getattr(row, "role", None) == "assistant" and isinstance(content, str):
            ids.extend(_marker_ids(content))
    return list(dict.fromkeys(ids))[-_MAX_IDS:]


async def _load(user_id: UUID, ids: list[UUID]) -> dict[UUID, ShownPicture]:
    # Imported here: the turn's read is imported where no database is (the SymPy pool).
    from app.core.db import SessionLocal
    from app.modules.attachments import service as attachments_service

    try:
        async with asyncio.timeout(_LOAD_SECONDS), SessionLocal() as session:
            rows = await attachments_service.get_by_ids(session, ids, user_id)
    except Exception as exc:  # A label is a hint: without it the line is said by its model.
        logger.info("picture labels not read (%s)", type(exc).__name__)
        return {}
    return {
        row.id: ShownPicture(source=row.source, label=(row.original_filename or None))
        for row in rows
    }


def start_labels(
    user_id: UUID | None, rows: Iterable[Any]
) -> asyncio.Task[dict[UUID, ShownPicture]] | None:
    """Read the labels of the pictures ``rows`` show, beside the turn; None with none.
    Kept for the turn, so its prompt reads the same answer (``labels_for_turn``)."""
    ids = picture_ids(rows)
    if user_id is None or not ids:
        return None
    task = asyncio.create_task(_load(user_id, ids), name="shown_pictures")
    keep_for_turn(_KEPT, task)
    return task


async def settled_labels(task: asyncio.Future[dict[UUID, ShownPicture]] | None) -> ShownPictures:
    """The labels ``task`` read, or none: it never raises, and is never cancelled here."""
    if task is None:
        return {}
    try:
        return await asyncio.shield(task)
    except Exception as exc:  # A label is a hint, as above.
        logger.info("picture labels not read (%s)", type(exc).__name__)
        return {}


async def labels_for_turn() -> ShownPictures:
    """The labels this turn started reading (``start_labels``), or none."""
    kept = kept_for_turn(_KEPT)
    return await settled_labels(kept if isinstance(kept, asyncio.Future) else None)


def _clip(label: str | None) -> str:
    text = " ".join((label or "").split())
    return text[:_LABEL_CHARS]


def _said(picture: ShownPicture | None, model: str | None) -> str:
    """One shown picture, said in words."""
    source = picture.source if picture is not None else None
    label = _clip(picture.label if picture is not None else None)
    if source == "generated" or (source is None and model == _GENERATED_MODEL):
        what = f' from the prompt "{label}"' if label else ""
        return f"(Shown here: a picture the app generated for the user{what}.)"
    if source == "search" or (source is None and model == _PHOTO_MODEL):
        what = f' of "{label}"' if label else ""
        return f"(Shown here: a photo the app found for the user{what}.)"
    return "(Shown here: a picture.)"


def as_text(content: str, *, model: str | None, pictures: ShownPictures) -> str:
    """An assistant row with each picture line said in words; any other text kept."""
    if "[Image:" not in content:
        return content
    out: list[str] = []
    for line in content.splitlines():
        ids = _marker_ids(line)
        if ids and line.strip().startswith("[Image:"):
            out.append(" ".join(_said(pictures.get(uid), model) for uid in ids))
        else:
            out.append(line)
    return "\n".join(out)
