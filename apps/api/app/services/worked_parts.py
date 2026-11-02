"""One layout for a worked answer in parts, whoever worked it.

A question in parts reads as a single worked answer does, once:

- **Given**: every part's givens, each value once, closed by one ``where`` line
- **Required**: one line per part, ``(a) $v$ — speed after 1 s``
- **Solution**, then each part: its label (``**(a) Speed after 1 s**``), its formula
  under its name's heading, its substitution or steps, and **Answer (a)** with that part's
  card; a hairline between parts

Physics' own parts (``modules/physics/direct.py``), the separate questions of one message
solved one by one (``services/subjects/dispatch.py``) and the model-written ```worked
block in parts (``modules/chat/worked_render.py``) all render here. Before November 2026
the separate questions came back as whole replies one after another: the givens repeated
under each part, the part above its givens, and no card under any answer (the finalize
pass for one verified part dropped the others').
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.services.workout import ANSWER, GIVEN, REQUIRED, REQUIRED_HEADINGS, SOLUTION

_HARD_BREAK = "  \n"
_NOTE = " — "
# "$v_0$ = initial speed" or "$m_1$, $m_2$ = masses": one name in a where-line.
_WHERE_PIECE = re.compile(r"[,;] (?=\$[^$]+\$(?:, \$[^$]+\$)* = )")


@dataclass(frozen=True)
class WorkedPart:
    """One part. ``working``: its rendered sections, from the formula to the last line
    before its answer. ``answer``: its card's body, or None when the value follows the
    heading as a line (``after``) for finalize to card. ``after``: what follows the card
    (a picture)."""

    title: str
    working: str
    answer: str | None = None
    after: str = ""
    required: tuple[str, ...] = ()
    given: tuple[str, ...] = ()


def part_letter(index: int) -> str:
    """``a``, ``b``, … for a part; past ``z`` its number, so no part is ever dropped."""
    return chr(ord("a") + index) if index < 26 else str(index + 1)


def _section(heading: str, lines: Sequence[str]) -> str:
    return f"**{heading}**{_HARD_BREAK}" + _HARD_BREAK.join(lines)


def _where_pieces(line: str) -> list[str]:
    """``$a$ = x, $b$, $c$ = ys`` → ``["$a$ = x", "$b$, $c$ = ys"]``: a comma between two
    symbols of one meaning is no cut."""
    text = line.removeprefix("where ")
    pieces: list[str] = []
    start = 0
    for cut in _WHERE_PIECE.finditer(text):
        if " = " in text[start : cut.start()]:
            pieces.append(text[start : cut.start()].strip())
            start = cut.end()
    pieces.append(text[start:].strip())
    return [piece for piece in pieces if piece]


def merged_given(lines: Sequence[str]) -> list[str]:
    """Each given once, in order, then one ``where`` line naming every symbol once."""
    values: list[str] = []
    names: list[str] = []
    for line in lines:
        text = line.strip()
        if text.startswith("where "):
            names.extend(piece for piece in _where_pieces(text) if piece not in names)
        elif text and text not in values:
            values.append(text)
    if names:
        grouped = any(re.search(r"\$, \$", piece) for piece in names)
        values.append(f"where {('; ' if grouped else ', ').join(names)}")
    return values


def _what(title: str) -> str:
    """``Speed after 1 s`` → ``speed after 1 s``: what a part finds, after a dash."""
    text = title.strip().rstrip("?.:")
    if len(text) > 1 and text[0].isupper() and not text[1].isupper():
        return text[0].lower() + text[1:]
    return text


def _required_line(letter: str, line: str, title: str) -> str:
    """``(a) $v$ — speed after 1 s``: the part's letter, what it finds and what that is."""
    if _NOTE in line or not title.strip():
        return f"({letter}) {line}"
    return f"({letter}) {line}{_NOTE}{_what(title)}"


def render_parts(
    parts: Sequence[WorkedPart], given: Sequence[str] = (), *, required: Sequence[str] = ()
) -> str:
    """The question in parts in the one layout: Given and Required once, then Solution and
    each part closed by its own Answer and card. ``required``: lines no part owns."""
    givens = merged_given([*given, *(line for part in parts for line in part.given)])
    asked = [
        *required,
        *(
            _required_line(part_letter(index), line, part.title)
            for index, part in enumerate(parts)
            for line in part.required
        ),
    ]
    opening = [
        _section(heading, lines) for heading, lines in ((GIVEN, givens), (REQUIRED, asked)) if lines
    ]
    sections: list[str] = []
    for index, part in enumerate(parts):
        letter = part_letter(index)
        label = f"**({letter}) {part.title.strip().rstrip('?')}**" if part.title.strip() else ""
        pieces = [label, part.working.strip()]
        # A part still streaming has no answer yet: its heading waits with it.
        if part.answer is not None or part.after.strip():
            pieces.append(f"**{ANSWER} ({letter})**")
        if part.answer is not None:
            pieces.append(f"```answer\n{part.answer.strip()}\n```")
        pieces.append(part.after.strip())
        sections.append("\n\n".join(piece for piece in pieces if piece))
    head = "\n\n".join([*opening, f"**{SOLUTION}**"]) if opening else ""
    body = "\n\n---\n\n".join(sections)
    return f"{head}\n\n{body}" if head else body


_FENCE_OPEN = re.compile(r"^```answer[ \t]*$", re.MULTILINE)
_HEADING = re.compile(r"^\*\*(?P<title>[^*\n]+)\*\*(?:  )?$")


@dataclass(frozen=True)
class _Read:
    given: tuple[str, ...]
    required: tuple[str, ...]
    working: str
    answer: str
    after: str


def read_worked_reply(reply: str) -> _Read | None:
    """A whole worked reply the server wrote, back in its sections; None for any other
    shape (a lead sentence, no Answer heading, no card), which is then shown as written."""
    head, found, tail = reply.strip().partition(f"\n\n**{ANSWER}**\n\n")
    if not found or not _FENCE_OPEN.match(tail):
        return None
    close = tail.find("\n```", len("```answer"))
    if close < 0:
        return None
    answer = tail[len("```answer") : close].strip("\n")
    after = tail[close + len("\n```") :].strip()
    given: tuple[str, ...] = ()
    required: tuple[str, ...] = ()
    working: list[str] = []
    for block in head.split("\n\n"):
        first, _, rest = block.partition("\n")
        heading = _HEADING.match(first)
        title = heading.group("title") if heading else ""
        lines = tuple(
            line.strip() for line in rest.replace("  \n", "\n").split("\n") if line.strip()
        )
        if title == GIVEN and not working:
            given = lines
        elif title in REQUIRED_HEADINGS and not working:
            required = lines
        elif title == SOLUTION and not working:
            continue
        elif not given and not required:
            return None  # a lead before the givens: not the worked layout
        else:
            working.append(block)
    if not required or not working:
        return None
    return _Read(given, required, "\n\n".join(working), answer, after)


def _short_title(question: str) -> str:
    """What a separate question finds, short: "What's its speed after 1 s?" → "Speed after
    1 s"; "How long to reach the ground?" → "Time to reach the ground"."""
    text = question.strip().rstrip("?.!").strip()
    for pattern, lead in _QUESTION_LEADS:
        match = pattern.match(text)
        if match is not None:
            text = lead + text[match.end() :]
            break
    return text[:1].upper() + text[1:] if text else text


_QUESTION_LEADS = (
    (re.compile(r"^how long (?:does it take |will it take |is it )?(?=to\b)", re.I), "time "),
    (re.compile(r"^how long\b", re.I), "time"),
    (re.compile(r"^how far\b", re.I), "distance"),
    (re.compile(r"^how fast\b", re.I), "speed"),
    (re.compile(r"^how high\b", re.I), "height"),
    (
        re.compile(
            r"^(?:what(?:'s| is| was| will be| are)|find|calculate|determine|work out)\s+"
            r"(?:the |its |their |his |her |this |that )?",
            re.I,
        ),
        "",
    ),
)


def parts_in_one_layout(questions: Sequence[str], replies: Sequence[str]) -> str | None:
    """Separate questions' worked replies as one question in parts; None when a reply is
    not the worked layout."""
    parts: list[WorkedPart] = []
    for question, reply in zip(questions, replies, strict=True):
        read = read_worked_reply(reply)
        if read is None:
            return None
        parts.append(
            WorkedPart(
                title=_short_title(question),
                working=read.working,
                answer=read.answer,
                after=read.after,
                required=read.required,
                given=read.given,
            )
        )
    return render_parts(parts)
