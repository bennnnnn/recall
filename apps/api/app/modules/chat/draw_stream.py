"""A ```draw block kept out of the live stream: the phone never sees a description.

On a maths turn asking to see a picture the reply may describe it in a ```draw block, JSON
the server checks and draws once the reply is done (``math.drawing``, ``figure_turn``).
The phone shows a fence it does not know as code, so the block is held back as it streams
and kept aside on the turn's accumulator; the text around it streams as it was written. A
line that could still become the block's opener waits for its end, so no opener goes out
in pieces. A block that never closes is never shown either.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from app.modules.chat.stream_accum import StreamAccum
from app.services.md_fence_scan import FenceMarker, read_fence_marker

_LANG = "draw"
# The start of a line that may still become a fence line: up to three spaces, then a run of
# three or more backticks or tildes, or a shorter run with nothing after it yet. "`useEffect`
# runs…" or "~5 min later" can never open one and streams at once (review of #2462).
_MAY_BE_FENCE = re.compile(r"^ {0,3}(?:`{3,}|~{3,}|`{1,2}$|~{1,2}$)")


def _may_open(partial: str) -> bool:
    """Whether a line still being written could become a fence line (a block's opener, or
    an outer fence's)."""
    return _MAY_BE_FENCE.match(partial) is not None or partial in {" ", "  ", "   "}


class DrawScan:
    """The one rule for what a ```draw block is, live and in a saved reply: a ```draw (or
    ~~~draw) line opens one outside any other fence ("````markdown" around an example keeps
    it as content), a bare fence line of either kind closes it, and one never closed runs to
    the reply's end. ``feed`` each piece; it returns the text around the blocks."""

    def __init__(self, keep: Callable[[str], None]) -> None:
        self._keep_body = keep
        self._line = ""
        # Part of the current line went out already: the rest of it is no fence line.
        self._mid = False
        self._outer: FenceMarker | None = None
        self._fence: FenceMarker | None = None
        self._body: list[str] = []

    def feed(self, chunk: str) -> str:
        self._line += chunk
        out: list[str] = []
        while "\n" in self._line:
            line, self._line = self._line.split("\n", 1)
            out.append(self._take(line, "\n"))
            self._mid = False
        if self._line and self._fence is None and (self._mid or not _may_open(self._line)):
            out.append(self._line)
            self._line, self._mid = "", True
        return "".join(out)

    def flush(self) -> str:
        """The stream ended: a line left over is read (a block's closer with no newline
        after it closes it); a block still open is kept, unshown."""
        line, self._line = self._line, ""
        sent = self._take(line, "") if line else ""
        if self._fence is not None:
            self._keep()
        return sent

    def _take(self, line: str, end: str) -> str:
        if self._mid:
            return line + end
        marker = read_fence_marker(line)
        if self._fence is not None:
            if marker is not None and not marker.info:
                self._keep()
            else:
                self._body.append(line)
            return ""
        if self._outer is not None:
            if marker is not None and marker.closes(self._outer):
                self._outer = None
            return line + end
        if marker is not None and marker.lang == _LANG:
            self._fence, self._body = marker, []
            return ""
        if marker is not None:
            self._outer = marker
        return line + end

    def _keep(self) -> None:
        body = "\n".join(self._body).strip()
        if body:
            self._keep_body(body)
        self._fence, self._body = None, []


def without_draw_blocks(text: str) -> tuple[str, list[str]]:
    """``text`` without its ```draw blocks, and their bodies: the rule the stream keeps."""
    bodies: list[str] = []
    scan = DrawScan(bodies.append)
    return scan.feed(text) + scan.flush(), bodies


class DrawFilter:
    """``feed`` each piece of the reply; it returns what the client may be sent. Each block
    is kept on the accumulator, at the place in the shown text it stood."""

    def __init__(self, accum: StreamAccum) -> None:
        self._accum = accum
        self._scan = DrawScan(lambda body: accum.drawings.append((len(accum.shown), body)))

    def feed(self, chunk: str) -> str:
        return self._scan.feed(chunk)

    def flush(self) -> str:
        return self._scan.flush()
