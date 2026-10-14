"""A real photo above an answer about something worth seeing.

The model opens such a reply with a ```photo fence holding a short image
search ("Ethiopia location map", "capybara"). The search starts as soon as
that fence closes, while the rest of the answer streams. When the reply is
done the fence becomes the app's ``[Image: …]`` marker, or disappears when
no photo was found. The phone hides the fence until then.
"""

from __future__ import annotations

import asyncio
import logging
import re
from uuid import UUID

from app.core.config import Settings
from app.models.orm import User
from app.modules.images import search as image_search

logger = logging.getLogger(__name__)

_PHOTO_FENCE = re.compile(
    r"^[ \t]*```photo[ \t]*\n(?P<query>[^\n`]{1,120})\n[ \t]*```[ \t]*(?:\n(?:[ \t]*\n)*|$)",
    re.IGNORECASE | re.MULTILINE,
)
# The fence opens the reply; a late one is still honored when the reply ends.
_WATCH_CHARS = 600
# The search usually finishes while the answer streams; never hold a reply long.
_WAIT_SECONDS = 6.0


def _marker(attachment_id: UUID) -> str:
    return f"[Image: /attachments/{attachment_id}/file]"


class AnswerPhoto:
    """Starts the photo search for one reply and swaps its fence for the photo."""

    def __init__(self, settings: Settings, user: User) -> None:
        self._settings = settings
        self._user = user
        self._task: asyncio.Task[list[UUID]] | None = None
        self._watching = True

    @property
    def watching(self) -> bool:
        """True until the reply's opening is past (or its photo search started)."""
        return self._watching

    def _start(self, query: str) -> asyncio.Task[list[UUID]]:
        self._task = asyncio.create_task(
            image_search.photos_for_answer(self._settings, user=self._user, query=query),
            name="answer_photo",
        )
        return self._task

    def feed(self, text: str) -> None:
        """Look at the reply so far; start the search once its photo fence closes."""
        if not self._watching:
            return
        match = _PHOTO_FENCE.search(text[:_WATCH_CHARS])
        if match is not None:
            self._watching = False
            self._start(match.group("query").strip())
        elif len(text) >= _WATCH_CHARS:
            self._watching = False

    async def attach(self, content: str) -> tuple[str, list[UUID]]:
        """The reply with its photo marker in place of the fence, and the photo ids."""
        match = _PHOTO_FENCE.search(content)
        if match is None:
            self.cancel()
            return content, []
        task = self._task or self._start(match.group("query").strip())
        ids: list[UUID] = []
        try:
            ids = await asyncio.wait_for(asyncio.shield(task), timeout=_WAIT_SECONDS)
        except TimeoutError:
            logger.info("Answer photo took too long; sending the reply without it")
            task.add_done_callback(_log_late_photo)
        except Exception:
            logger.exception("Answer photo failed")
        marker = "\n".join(_marker(attachment_id) for attachment_id in ids)
        first = True

        def replace(found: re.Match[str]) -> str:
            nonlocal first
            if first and marker:
                first = False
                return f"{marker}\n\n"
            return ""

        return _PHOTO_FENCE.sub(replace, content).strip(), ids

    def cancel(self) -> None:
        """Drop a search the reply no longer needs (stopped, failed, or no fence left)."""
        if self._task is not None and not self._task.done():
            self._task.cancel()


def _log_late_photo(task: asyncio.Task[list[UUID]]) -> None:
    # A photo that arrives after the reply was saved stays unlinked; the
    # attachment reaper removes it.
    if not task.cancelled() and task.exception() is not None:
        logger.warning("Late answer photo failed", exc_info=task.exception())


def strip_photo_fences(content: str) -> str:
    """The reply without any photo fence (when photos are off or the reply failed)."""
    return _PHOTO_FENCE.sub("", content).strip()
