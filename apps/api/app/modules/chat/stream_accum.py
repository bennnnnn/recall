"""A turn's reply text as it streams, and what a Stop keeps of it.

The finalize passes read what the client was sent (``shown``: the model's text
with its scaffolding removed), so a saved reply never holds text the phone did
not draw. A user's Stop also cuts it to what the client says it drew, so the
saved reply and the stopped bubble are the same text and nothing streams on
into it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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
    completion: str = "complete"

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
        client says it drew; tokens still in flight then were never seen."""
        shown = "".join(self.shown)
        if self.completion == "user_stop" and client_shown_chars is not None:
            shown = utf16_prefix(shown, client_shown_chars)
        return shown.strip()
