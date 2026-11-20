"""A question's labelled parts, for every subject: "(i) protons, (ii) neutrons, (iii) electrons".

A verified result answers one thing. A question in labelled parts asks several, so an
instant reply built from that one result drops the rest: "determine the number of
(i) protons, (ii) neutrons, (iii) electrons" was answered "N = 12" alone (2026-10-30).
"""

from __future__ import annotations

import re

# "(a)", "b)", "(ii)": a labelled part. Two or more distinct labels are parts.
_PART_LABEL = re.compile(r"(?:^|[\s,;:.?!])\(?([a-h]|i{1,3}|iv|vi{0,3})\)(?=\s)", re.IGNORECASE)

# Said to the model beside a verified result that answers one of those parts.
ONE_PART_NOTE = (
    "The question has more labelled parts than this verified result answers. "
    "Answer every part, in the question's order and under its own label, and use this "
    "result for its part."
)


def asks_more_parts(text: str, answers: str) -> bool:
    """``text`` has more labelled parts than ``answers`` has lines."""
    lines = [line for line in answers.splitlines() if line.strip()]
    return labelled_parts(text) > max(len(lines), 1)


def labelled_parts(text: str) -> int:
    """How many distinct part labels ``text`` has; 0 when fewer than two."""
    labels = {match.group(1).lower() for match in _PART_LABEL.finditer(text)}
    return len(labels) if len(labels) >= 2 else 0


def labelled_part_texts(text: str) -> tuple[str, tuple[str, ...]]:
    """The statement before the first label, and each labelled part's own words in order;
    no parts unless ``text`` has two distinct labels or more, each used once."""
    found = list(_PART_LABEL.finditer(text))
    labels = [match.group(1).lower() for match in found]
    if len(labels) < 2 or len(set(labels)) != len(labels):
        return text.strip(), ()
    # A label starts at its bracket, "(a)", or at its letter, "a)".
    starts = [
        match.start(1) - 1 if match.start(1) and text[match.start(1) - 1] == "(" else match.start(1)
        for match in found
    ]
    parts = tuple(
        text[match.end() : end].strip(" \t\n,;")
        for match, end in zip(found, [*starts[1:], len(text)], strict=True)
    )
    return text[: starts[0]].strip(), parts


def part_named(text: str, label: str) -> str | None:
    """The words of ``text``'s part labelled ``label`` ("b", "(ii)"), or None when it has no
    such part (or no labelled parts)."""
    _stem, parts = labelled_part_texts(text)
    if not parts:
        return None
    labels = [match.group(1).lower() for match in _PART_LABEL.finditer(text)]
    return dict(zip(labels, parts, strict=True)).get(label.strip("()").lower())


# A part's label as a line or a read names it: "b", "(b)", "part b", "(ii)".
_NAMED_LABEL = re.compile(r"^(?:part\s+)?\(?([a-h]|i{1,3}|iv|vi{0,3})\)?$", re.IGNORECASE)


def named_label(said: str) -> str | None:
    """The part label ``said`` names ("part b" is "b"), or None when it names no label."""
    found = _NAMED_LABEL.match(said.strip(" .:?"))
    return found.group(1).lower() if found else None


def with_only_part(text: str, label: str) -> str | None:
    """``text`` as one labelled part asks it: the statement before the labels and that part's
    own words; None when ``text`` has no part ``label``."""
    words = part_named(text, label)
    if words is None:
        return None
    stem, _parts = labelled_part_texts(text)
    return f"{stem} {words}".strip()
