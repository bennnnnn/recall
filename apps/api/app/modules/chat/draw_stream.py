"""A ```draw block kept out of the live stream: the phone never sees a description.

On a maths turn asking to see a picture the reply may describe it in a ```draw block, JSON
the server checks and draws once the reply is done (``math.drawing``, ``figure_turn``).
The phone shows a fence it does not know as code, so the block is held back as it streams
and kept aside on the turn's accumulator; the text around it streams as it was written. A
line that could still become the block's opener waits for its end, so no opener goes out
in pieces. A block that never closes is never shown either.
"""

from __future__ import annotations

from app.modules.chat.stream_accum import StreamAccum
from app.services.md_fence_scan import FenceMarker, read_fence_marker

_LANG = "draw"
_OPENERS = tuple(run * 3 + _LANG for run in "`~")


def _may_open(partial: str) -> bool:
    """Whether a line still being written could become a block's opener."""
    compact = partial.replace(" ", "").replace("\t", "").lower()
    return bool(partial) and any(
        opener.startswith(compact) or compact.startswith(opener) for opener in _OPENERS
    )


class DrawFilter:
    """``feed`` each piece of the reply; it returns what the client may be sent."""

    def __init__(self, accum: StreamAccum) -> None:
        self._accum = accum
        self._line = ""
        self._fence: FenceMarker | None = None
        self._body: list[str] = []

    def feed(self, chunk: str) -> str:
        self._line += chunk
        out: list[str] = []
        while "\n" in self._line:
            line, self._line = self._line.split("\n", 1)
            out.append(self._take(line, "\n"))
        if self._fence is None and not _may_open(self._line):
            out.append(self._line)
            self._line = ""
        return "".join(out)

    def flush(self) -> str:
        """The stream ended: a line left over is read; an open block is kept unshown."""
        line, self._line = self._line, ""
        if self._fence is None:
            return self._take(line, "")
        self._body.append(line)
        self._keep()
        return ""

    def _take(self, line: str, end: str) -> str:
        marker = read_fence_marker(line)
        if self._fence is None:
            if marker is not None and marker.lang == _LANG:
                self._fence, self._body = marker, []
                return ""
            return line + end
        if marker is not None and marker.closes(self._fence):
            self._keep()
        else:
            self._body.append(line)
        return ""

    def _keep(self) -> None:
        body = "\n".join(self._body).strip()
        if body:
            self._accum.drawings.append((len(self._accum.shown), body))
        self._fence, self._body = None, []
