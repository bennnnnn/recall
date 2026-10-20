"""One "Answer" label per answer, for every subject's reply a model wrote.

A follow-up copied its history and wrote **Answer**, then ``Answer: 26.3\\,\\mathrm{N·m}``
(the value as raw LaTeX), and the card under it drew a third label. Before a subject
lands its card (``land_answer_card``), this leaves one label:

- ``**Answer**`` and, under it, ``Answer: X``: the heading over ``X``, LaTeX as maths;
- in a worked one-part reply (Find, Formula, Substitution or Steps, or a card), only
  the last label: earlier bare headings go, and an earlier ``Answer: X`` keeps only its
  value, as working. A quiz's "**Answer:** 4" under each question is left alone;
- a reply in parts keeps one label per part (``**Answer (a)**``).

Code fences are left alone.
"""

from __future__ import annotations

import re

# **Answer**, **Answer:**, ## Answer, Answer: — alone on its line.
_HEADING = re.compile(r"^\s*(?:#{1,4}\s+)?(?:\*\*)?answer(?:\*\*)?\s*:?\s*(?:\*\*)?\s*:?\s*$", re.I)
# Answer: X, **Answer:** X, **Answer**: X — a label and its value on one line.
_INLINE = re.compile(r"^\s*(?:\*\*)?answer\s*(?:\*\*)?\s*:\s*(?:\*\*)?\s*(?P<value>\S.*)$", re.I)
# A part's label or its answer: **(a) Range**, **Part (b): Time**, **Answer (a)**.
_PART = re.compile(
    r"^\s*(?:#{1,4}\s+)?\*\*\s*(?:part\s+\(?[a-h]\)?|\(?[a-h]\)|answer\s*\([a-h]\))", re.I
)
_FENCE = re.compile(r"^\s*(?:`{3,}|~{3,})")
_WORKED = re.compile(
    r"^\s*\*\*(?:Find|Formula|Substitution|Steps):?\*\*|^\s*(?:`{3,}|~{3,})\s*answer\b", re.I | re.M
)


def _value(value: str) -> str:
    """The value as a line of its own: LaTeX written bare goes in maths."""
    text = value.strip()
    if text.endswith("**"):
        text = text[:-2].rstrip()
    return f"${text}$" if re.search(r"\\[A-Za-z]", text) and "$" not in text else text


def one_answer_label(text: str) -> str:
    """The reply with each answer labelled once (see the module docstring)."""
    lines = text.split("\n")
    outside = _outside_fences(lines)
    labels: list[int] = []
    for number, line in enumerate(lines):
        if number not in outside:
            continue
        if _HEADING.match(line):
            labels.append(number)
            continue
        inline = _INLINE.match(line)
        if inline is None:
            continue
        previous = _previous_text(lines, number)
        if previous is not None and previous in labels and _HEADING.match(lines[previous]):
            # Under its heading, "Answer: X" is X.
            lines[number] = _value(inline.group("value"))
        else:
            labels.append(number)
    if not _WORKED.search(text) or any(_PART.match(lines[number]) for number in outside):
        return "\n".join(lines)
    for number in labels[:-1]:
        inline = _INLINE.match(lines[number])
        lines[number] = _value(inline.group("value")) if inline else _DROP
    return "\n".join(_without_dropped(lines))


_DROP = "\x00"


def _without_dropped(lines: list[str]) -> list[str]:
    """Dropped headings out, with the blank line that followed each."""
    kept: list[str] = []
    skip_blank = False
    for line in lines:
        if line == _DROP:
            skip_blank = True
            continue
        if skip_blank and not line.strip():
            skip_blank = False
            continue
        skip_blank = False
        kept.append(line)
    return kept


def _previous_text(lines: list[str], number: int) -> int | None:
    for earlier in range(number - 1, -1, -1):
        if lines[earlier].strip():
            return earlier
    return None


def _outside_fences(lines: list[str]) -> set[int]:
    outside: set[int] = set()
    fence: str | None = None
    for number, line in enumerate(lines):
        marker = _FENCE.match(line)
        if fence is None:
            if marker:
                fence = marker.group(0).strip()[0] * 3
                continue
            outside.add(number)
        elif marker and line.strip().startswith(fence):
            fence = None
    return outside
