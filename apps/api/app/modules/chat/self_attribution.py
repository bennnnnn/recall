"""The reply never signs its own writing.

"Write me a two-line poem about rain" came back as the poem on ``>`` lines closed by
``— Recall`` (live, 2026-11-05): the quote card the prompt keeps for a cited quotation,
attributed to the assistant itself. A citation names who said the words; the assistant's
own name there means the words are its own. That line is dropped wherever it stands (in
the quote, just after it, or closing the reply), and the quote it closes becomes the
plain lines it holds, so a poem reads as a poem rather than a card. Nothing else is
removed, and a quotation of anyone else keeps its card and its citation.
"""

from __future__ import annotations

import re

from app.modules.chat.prompt_constants import ASSISTANT_NAME
from app.services.md_fence_scan import line_fences

# A citation line naming the assistant: ``> — Recall``, ``— *Recall*``, an en dash or ``--``
# for the em dash. A hyphen cites only inside a quote; outside one ``- Recall`` is a list item.
_SELF_SIGNED = re.compile(
    r"^[ \t]*(?:(?:>[ \t]*)+(?:\u2014|\u2013|--|-)|\u2014|\u2013|--)"
    rf"[ \t]*[*_]*{re.escape(ASSISTANT_NAME)}[*_]*[ \t.]*$",
    re.IGNORECASE,
)
_QUOTE = re.compile(r"^(?P<indent>[ \t]*)>[ \t]?")
# A quote's own citation line: "> — Gandhi", "> - Gandhi" (a hyphen cites on a quote line).
_CITES = re.compile(r"^[ \t]*(?:>[ \t]*)+(?:\u2014|\u2013|--|-)")


def _blank(line: str) -> bool:
    return not line.strip() or not _QUOTE.sub("", line, count=1).strip()


def _unquote(lines: list[str], end: int) -> None:
    """The quote whose last line is ``end``, written as the plain lines it holds, each kept
    at its indent. Only the quote the signature closed, inside it or on the line under it:
    across a blank line the quote may be anyone's (a "> Warning:" callout, Gandhi), and one
    with a citation of its own ("> — Gandhi", "> - Gandhi") is someone else's words. Those
    stay quotes; the signature alone goes (reviews of #2300)."""
    if end < 0 or _QUOTE.match(lines[end]) is None or _CITES.match(lines[end]):
        return
    start = end
    while start >= 0 and _QUOTE.match(lines[start]) is not None:
        start -= 1
    for index in range(start + 1, end + 1):
        quote = _QUOTE.match(lines[index])
        if quote is not None:
            lines[index] = quote.group("indent") + lines[index][quote.end() :]


def drop_self_attribution(text: str) -> str:
    """``text`` without a citation of the assistant, and the quote it closed unwrapped."""
    if ASSISTANT_NAME.casefold() not in text.casefold():
        return text
    lines = text.split("\n")
    owners = line_fences(text)
    signed = [
        index
        for index, line in enumerate(lines)
        if owners[index] is None and _SELF_SIGNED.match(line) is not None
    ]
    if not signed:
        return text
    for index in reversed(signed):
        del lines[index]
        # A citation between two blank lines leaves one of them.
        if 0 < index < len(lines) and not lines[index].strip() and not lines[index - 1].strip():
            del lines[index]
        above = index - 1
        # A blank quote line left above the citation goes with it.
        while above >= 0 and _QUOTE.match(lines[above]) is not None and _blank(lines[above]):
            del lines[above]
            above -= 1
        _unquote(lines, above)
    # A citation that closed the reply leaves no blank lines behind it.
    return "\n".join(lines).rstrip() + text[len(text.rstrip()) :]
