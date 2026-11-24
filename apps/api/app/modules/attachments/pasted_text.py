"""Text the user pasted into the composer, sent as a plain-text file.

A paste of more than a couple of thousand characters leaves the phone's composer as a
``.txt`` attachment (``apps/mobile/features/attachments/model/pastedText.ts``), uploaded
like any document. The phone names that file ``PASTED_TEXT_FILENAME``; the name and the
``text/plain`` type together are how the server knows the text was pasted, not picked.

The model reads it as it would the same text typed: up to a message's length inline
(another document gets ``MAX_EXTRACT_CHARS``), the rest through retrieval as with any
document. One paste holds at most what a document is searchable up to; a longer one is
refused here as on the phone, never cut short without a word.
"""

from __future__ import annotations

from app.models.schemas.chats import MESSAGE_MAX_CHARS
from app.modules.attachments.content_types import normalize_content_type
from app.modules.attachments.text_extract import MAX_INDEX_EXTRACT_CHARS
from app.services.prompt_safety import PASTED_TEXT_HEADER

PASTED_TEXT_FILENAME = "pasted-text.txt"
PASTED_TEXT_CONTENT_TYPE = "text/plain"

# Read inline: as much as a typed message may hold.
PASTED_TEXT_INLINE_CHARS = MESSAGE_MAX_CHARS

# The most one paste may hold: what a document is searchable up to.
PASTED_TEXT_MAX_CHARS = MAX_INDEX_EXTRACT_CHARS

# UTF-8 takes at most four bytes a character, so a declared size past this is too long
# before a byte is read. The exact count is taken when a turn reads the file.
PASTED_TEXT_MAX_BYTES = PASTED_TEXT_MAX_CHARS * 4

PASTE_TOO_LONG_MESSAGE = (
    f"Pasted text can be at most {PASTED_TEXT_MAX_CHARS:,} characters. Attach it as a file instead."
)


def is_pasted_text(content_type: str, filename: str | None) -> bool:
    """Whether an attachment is text the phone's composer turned into a file."""
    return (
        filename == PASTED_TEXT_FILENAME
        and normalize_content_type(content_type) == PASTED_TEXT_CONTENT_TYPE
    )


def pasted_text_in(attachment_lines: list[str]) -> str:
    """The pasted text a turn's attachment lines hold (``format_attachment_lines``), without
    the model's note on how much was read: what the turn's readers read as its words."""
    texts: list[str] = []
    for line in attachment_lines:
        head, _, body = line.partition("\n")
        if head != PASTED_TEXT_HEADER:
            continue
        if body.startswith("[File note:"):
            body = body.partition("\n")[2]
        texts.append(body.strip())
    return "\n\n".join(text for text in texts if text)


def pasted_text_too_long(data: bytes) -> bool:
    """Whether a pasted file's text holds more characters than one paste may."""
    if len(data) <= PASTED_TEXT_MAX_CHARS:
        return False  # never more characters than bytes
    return len(data.decode("utf-8", errors="replace")) > PASTED_TEXT_MAX_CHARS
