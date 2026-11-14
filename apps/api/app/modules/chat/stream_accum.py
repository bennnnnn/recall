"""A turn's reply text as it streams, and what a Stop keeps of it.

The finalize passes read what the client was sent (``shown``: the model's text
with its scaffolding removed), so a saved reply never holds text the phone did
not draw. A user's Stop also cuts it to what the client says it drew, so the
saved reply and the stopped bubble are the same text and nothing streams on
into it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# How a reply ended: whole, cut short (provider, length or a server stop), or stopped
# by its user. ``done`` sends the last two as ``completion``.
Completion = Literal["complete", "interrupted", "user_stop"]

# A client's report of how much it drew is a UTF-16 length (a JS string's).
_UTF16 = "utf-16-le"


def utf16_prefix(text: str, units: int) -> str:
    """The first ``units`` UTF-16 code units of ``text``, never half a character."""
    encoded = text.encode(_UTF16)
    if units * 2 >= len(encoded):
        return text
    return encoded[: max(0, units) * 2].decode(_UTF16, errors="ignore")


@dataclass
class StreamAccum:
    # The model's text as it arrived.
    parts: list[str] = field(default_factory=list)
    # The text the client was sent: scaffolding removed (``ScaffoldFilter``).
    shown: list[str] = field(default_factory=list)
    was_cancelled: bool = False
    completion: Completion = "complete"
    # Text taken back, in order, as (the model's text, the text the client was sent): a
    # first answer that denied live facts (``tool_loop.live_denial``), which the phone takes
    # down, then text a search's answer replaces, which it shows until ``done``. The client
    # drew both, so ``done`` carries the reply in their place.
    taken_back: list[tuple[str, str]] = field(default_factory=list)
    # Nothing came in the place of text taken back and the last of it came back
    # (``restore_retracted``): ``done`` carries it, as the client's bubble may not hold it.
    restored: bool = False
    # The reply stopped extending what the client was sent (a ```worked block laid out
    # again when a record came out of order, ``worked_stream``): ``done`` carries it.
    rewritten: bool = False

    @property
    def retracted(self) -> str:
        """The text taken back, as the client was sent it."""
        return "".join(shown for _parts, shown in self.taken_back)

    def retract(self, parts_from: int, shown_from: int) -> None:
        taken = ("".join(self.parts[parts_from:]), "".join(self.shown[shown_from:]))
        self.taken_back.append(taken)
        del self.parts[parts_from:], self.shown[shown_from:]

    def restore_retracted(self) -> None:
        """A stop or a failure left nothing in the place of text taken back: the last of it
        the client still shows comes back, so the saved reply is the phone's. That is text a
        search's answer was to replace, which the phone keeps until ``done``, or else the
        denial the phone took down, which it puts back when nothing replaced it (its turn
        reducer's Stop, ``chatTurnState``; ``done`` carries it after a failure)."""
        if "".join(self.shown).strip():
            return
        for index in range(len(self.taken_back) - 1, -1, -1):
            parts, shown = self.taken_back[index]
            if shown.strip():
                del self.taken_back[index]
                self.parts.append(parts)
                self.shown.append(shown)
                self.restored = True
                return

    def mark_user_stop(self) -> None:
        self.was_cancelled = True
        if self.completion == "complete":
            self.completion = "user_stop"

    def mark_interrupted(self) -> None:
        self.was_cancelled = True
        if self.completion == "complete":
            self.completion = "interrupted"

    def mark_truncated(self) -> None:
        if self.completion == "complete":
            self.completion = "interrupted"

    def mark_server_stop(self) -> None:
        """The server stopped the reply (shutdown), whatever the stop looked like."""
        self.was_cancelled = True
        self.completion = "interrupted"

    def reply_text(self, client_shown_chars: int | None = None) -> str:
        """The text to finalize: what the client was sent, so the saved reply is
        the one the phone drew. After the user's Stop it is cut to the length the
        client says it drew; tokens still in flight then were never seen. Text taken
        back stays on the phone until text drawn after it replaces it (a denial it took
        down comes back on a Stop, ``chatTurnState``), so the reply is the last piece
        the client drew anything of: the answer, else what was taken back."""
        shown = "".join(self.shown)
        # After a rewrite the client's count is of other text: the reply is kept whole,
        # and ``done`` carries it (``rewritten``).
        stopped = self.completion == "user_stop" and not self.rewritten
        if not stopped or client_shown_chars is None:
            return shown.strip()
        # The client counted everything it was sent, in order: what was taken back, then
        # the answer.
        left, drawn = client_shown_chars, []
        for piece in [*(text for _model_text, text in self.taken_back), shown]:
            drawn.append(utf16_prefix(piece, max(0, left)).strip())
            left -= len(piece.encode(_UTF16)) // 2
        return next((text for text in reversed(drawn) if text), "")
