"""A real photo above an answer about something worth seeing.

The model opens such a reply with a ```photo fence holding a short image
search ("Ethiopia location map", "capybara"). The search starts as soon as
that fence closes, while the rest of the answer streams. When the reply is
done the fence becomes the app's ``[Image: …]`` marker, or disappears when
no photo was found. The phone hides the fence until then.

A search still running when the reply ends is not dropped: the reply goes out
without the fence, and the photo follows it (``follow``) for up to
``LATE_PHOTO_SECONDS`` from the reply's end, put above the saved reply by
``chat/late_photo``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID

from app.core.config import Settings
from app.models.orm import User
from app.modules.attachments.markers import image_marker
from app.modules.images import search as image_search
from app.services.md_fence_scan import iter_fences

logger = logging.getLogger(__name__)

# The fence holds one short line: what to look up.
_QUERY_CHARS = 120
# The fence opens the reply; a late one is still honored when the reply ends.
_WATCH_CHARS = 600
# The search usually finishes while the answer streams; never hold a reply long. The owner
# chose 2 s on 2026-11-09 (it was 6 s): a photo still on its way now follows the reply
# (``follow``), so a longer hold only delays the reply's buttons and follow-up questions.
_WAIT_SECONDS = 2.0
# A photo still on its way follows the reply until this long after the reply ended
# (the wait above included); then its search stops and the reply stays without one.
# The phone keeps its placeholder a little longer (ANSWER_PHOTO_WAIT_MS, wsConnect.ts).
LATE_PHOTO_SECONDS = 20.0


def _photo_fences(text: str) -> list[tuple[int, int, str]]:
    """Each closed ```photo fence holding one short line: (start, end, query). The end
    takes the blank lines after the fence."""
    found: list[tuple[int, int, str]] = []
    for fence in iter_fences(text):
        if not fence.closed or fence.lang != "photo":
            continue
        query = text[fence.body_start : fence.body_end].strip()
        if not query or len(query) > _QUERY_CHARS or "\n" in query or "`" in query:
            continue
        end = fence.end
        while (newline := text.find("\n", end)) >= 0 and not text[end:newline].strip():
            end = newline + 1
        found.append((fence.start, end, query))
    return found


def _replace_photo_fences(content: str, marker: str = "") -> str:
    """The reply with its first photo fence as ``marker`` and every other one gone."""
    pieces: list[str] = []
    cursor = 0
    for index, (start, end, _query) in enumerate(_photo_fences(content)):
        pieces.append(content[cursor:start])
        if index == 0 and marker:
            pieces.append(f"{marker}\n\n")
        cursor = end
    pieces.append(content[cursor:])
    return "".join(pieces).strip()


class AnswerPhoto:
    """Starts the photo search for one reply and swaps its fence for the photo."""

    def __init__(self, settings: Settings, user: User) -> None:
        self._settings = settings
        self._user = user
        self._task: asyncio.Task[list[UUID]] | None = None
        self._watching = True
        # When the reply went out with its photo still on its way: the search's deadline.
        self._late_until: float | None = None
        self._dropped = False

    @property
    def watching(self) -> bool:
        """True until the reply's opening is past (or its photo search started)."""
        return self._watching

    @property
    def late(self) -> bool:
        """The reply went out while its photo was still being looked up: it ``follow``s."""
        return self._late_until is not None and not self._dropped

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
        found = _photo_fences(text[:_WATCH_CHARS])
        if found:
            self._watching = False
            self._start(found[0][2])
        elif len(text) >= _WATCH_CHARS:
            self._watching = False

    async def attach(self, content: str) -> tuple[str, list[UUID]]:
        """The reply with its photo marker in place of the fence, and the photo ids.

        A search still running after ``_WAIT_SECONDS`` keeps running: the reply goes
        without the fence and the photo ``follow``s it (``late``).
        """
        found = _photo_fences(content)
        if not found:
            self.cancel()
            return content, []
        task = self._task or self._start(found[0][2])
        ids: list[UUID] = []
        reply_ended = time.monotonic()
        try:
            ids = await asyncio.wait_for(asyncio.shield(task), timeout=_WAIT_SECONDS)
        except TimeoutError:
            logger.info("Answer photo is still on its way; the reply goes first")
            self._late_until = reply_ended + LATE_PHOTO_SECONDS
        except asyncio.CancelledError:
            task.cancel()
            raise
        except Exception:
            logger.exception("Answer photo failed")
        marker = "\n".join(image_marker(attachment_id) for attachment_id in ids)
        return _replace_photo_fences(content, marker), ids

    async def follow(self) -> list[UUID]:
        """The late photo's ids once its search ends; [] when it fails, was dropped, or
        runs past ``LATE_PHOTO_SECONDS`` (then it is stopped, and its stored bytes and the
        day's lookup are given back as on any failure)."""
        task = self._task
        if task is None or self._late_until is None or self._dropped:
            return []
        try:
            return await asyncio.wait_for(task, timeout=self._late_until - time.monotonic())
        except TimeoutError:
            logger.info("Late answer photo ran out of time; the reply stays without it")
        except asyncio.CancelledError:
            # The search was dropped (a Stop, a deleted chat); a cancel of this wait goes on.
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise
        except Exception:
            logger.exception("Late answer photo failed")
        return []

    def cancel(self) -> None:
        """Drop a search the reply no longer needs (stopped, failed, no fence left, or
        its chat deleted)."""
        self._dropped = True
        if self._task is not None and not self._task.done():
            self._task.cancel()


def strip_photo_fences(content: str) -> str:
    """The reply without any photo fence (when photos are off or the reply failed)."""
    return _replace_photo_fences(content)
