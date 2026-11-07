"""A worked solution states its result once, after the working, never above it.

Told to answer first, a model opened worked replies with a number it had not worked yet:
"The ratio of fuel used … is **5 : 7**" over working and a card that found 4 : 5, and
"The car covers **290 m**" over a sum of 310 m (a Class 9 book, 2026-10-30); the prompt
saying a calculation opens with its working did not hold. Right, it said the answer twice:
"**x = 3**" over Given, Required, Solution and a card showing x = 3 (2026-11-07), where a
textbook, and the reply's own layout, give the result once, at the end. In a reply with a
worked section (Given, Working, Solution, Required, Formula, Substitution or Steps) and an
answer card below it, a short lead above the section stating a number the working never
reaches (a guess) or what a card says (the answer, early: "x = 3", or "25 m" with its
unit) goes. A digit the card shares is not enough: "Let's solve 5x - 3 = 12 for x." over
a card of x = 3 states no result. A heading, a photo, a part, a note or a lead with
neither stays ("the car does not reach 100 m in 5 s" over a card of 25 m), and so does a
long lead, which may be an answer of its own.

Below the cards it is not said again either (``drop_restated_tail``): asked to write
nothing outside its ```worked block, a model still closed with "The car's speed is
**20 m/s**, and the train's speed is **30 m/s**." under two cards showing just that
(2026-11-02). A short paragraph after the last card that states only the cards' numbers,
in words the reply or the question already holds, goes; a picture, or a sentence with a
number or a word of its own (a caveat, a direction the card lacks), stays.
"""

from __future__ import annotations

import re

from app.services.answer_fence import (
    ANSWER_FENCE_LANGS,
    UNCHECKED_ANSWER_MARKER,
    answer_fence_value,
)
from app.services.md_fence_scan import iter_fences, line_fences
from app.services.workout import REQUIRED_PATTERN

# The first label of the working, as a heading or a bare line: **Given**, **Working**,
# ## Solution, "Given". Replies label it several ways; the guess sits above any of them.
_GIVEN = re.compile(
    rf"^[^\S\n]*(?:#{{1,4}}[^\S\n]+)?(?:\*\*)?(?:Given|Working|Solution|{REQUIRED_PATTERN}|Formula"
    r"|Substitution|Steps)(?:\*\*)?:?(?:\*\*)?[^\S\n]*$",
    re.I | re.M,
)
# A heading: "## Stage 1", "**Atomic structure of Mg**"; a bold sentence ("**The ratio is
# 1 : 5.**") is a statement, and so is a bold value ("**x = 3**", "**25 m**": ``_a_heading``).
_HEADING = re.compile(r"^\s*(?:#{1,6}\s|\*\*[^*]*[^*.!?\s]\*\*\s*$)")
_VALUE_SIGN = re.compile(r"[=≈]")
# A number with its unit ("25 m", "9.8m/s"): a value, where "Q7" or "Ex 4" names a part.
_NUMBER_WITH_UNIT = re.compile(r"\d\s*[^\W\d_]")
# Not a stated result: a photo, an image, a list, a table, display maths, a part's label,
# a note or a warning.
_KEEP = re.compile(
    r"^\s*(?:\[Image:|!\[|[-*+]\s|\d+[.)]\s|\||\$\$|\\\[|\(?[a-h]\)|\(?[ivx]+\)|\*\*\s*(?:part|\(?[a-h]\))"
    r"|(?:\*\*)?(?:note|warning|tip|remember|caution|assume|assumption)s?\b)",
    re.I,
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# "4 : 5", "4/5", "\frac{4}{5}": a ratio is its pair, not two numbers any working holds.
_RATIO = re.compile(r"(\d+)\s*[:/]\s*(\d+)|\\[dt]?frac\{(\d+)\}\{(\d+)\}")
# "(15 milliseconds)": the same value in another unit, which the working need not reach.
_ASIDE = re.compile(r"\([^()]*\)")
_MOST_WORDS = 60


def _paragraphs(lead: str) -> list[tuple[int, int]]:
    """Each paragraph's (start, end) in ``lead``."""
    spans: list[tuple[int, int]] = []
    start = 0
    for gap in re.finditer(r"\n[^\S\n]*\n", lead):
        spans.append((start, gap.start()))
        start = gap.end()
    spans.append((start, len(lead)))
    return [(begin, end) for begin, end in spans if lead[begin:end].strip()]


def _numbers(text: str) -> set[str]:
    """The numbers ``text`` states, each ratio as one ("4:5")."""
    ratios = {
        f"{match.group(1) or match.group(3)}:{match.group(2) or match.group(4)}"
        for match in _RATIO.finditer(text)
    }
    plain = {number.replace(",", "") for number in _NUMBER.findall(_RATIO.sub(" ", text))}
    return ratios | plain


# A card's value as a lead would write it, flattened: no LaTeX wrappers, spacing commands
# or markup; no gap around "=" or between a number and its unit; words stay apart.
_LATEX_WRAPPER = re.compile(r"\\(?:text|mathrm|operatorname)\{([^{}]*)\}")
_LATEX_SPACING = re.compile(r"\\[,;:! ]")
_MARKUP = re.compile(r"[$*`{}]")
_AROUND_EQUALS = re.compile(r"\s*=\s*")
_NUMBER_UNIT_GAP = re.compile(r"(\d)\s+(?=[^\W\d_])")
_MINUS_SIGN = "\u2212"
# A card's protocol line ("part: a"), not what it says.
_CARD_META = re.compile(r"^[a-z]+:\s", re.I)
_UNIT_LETTER = re.compile(r"[^\W\d_]")


def _flat(text: str) -> str:
    text = _MARKUP.sub("", _LATEX_SPACING.sub(" ", _LATEX_WRAPPER.sub(r"\1", text)))
    text = _NUMBER_UNIT_GAP.sub(r"\1", _AROUND_EQUALS.sub("=", text.replace(_MINUS_SIGN, "-")))
    return " ".join(text.split()).lower()


def _card_statements(text: str) -> set[str]:
    """What the cards say, flattened: each "x=3" whole, and a value with its unit ("25m").
    A bare number is not a statement: the question may hold it too."""
    said: set[str] = set()
    for fence in iter_fences(text):
        if fence.lang not in ANSWER_FENCE_LANGS:
            continue
        for line in answer_fence_value(text[fence.body_start : fence.body_end]).splitlines():
            flat = _flat(line)
            if not flat or _CARD_META.match(line.strip()):
                continue
            if "=" in flat:
                said.add(flat)
            value = flat.rsplit("=", 1)[-1]
            if _NUMBER.search(value) and _UNIT_LETTER.search(value):
                said.add(value)
    return said


def _says_whole(text: str, statement: str) -> bool:
    """``statement`` stands whole in ``text``: "x=3" is not in "x=30", "25m" not in "125m"."""
    start = text.find(statement)
    while start >= 0:
        before = text[start - 1 : start]
        after = text[start + len(statement) : start + len(statement) + 2]
        joined_before = bool(before) and (before.isalnum() or before in "._")
        joined_after = bool(after) and (
            after[0].isalnum() or after[0] == "_" or (after[0] in ".," and after[1:2].isdigit())
        )
        if not joined_before and not joined_after:
            return True
        start = text.find(statement, start + 1)
    return False


def _a_heading(line: str) -> bool:
    """A heading names something ("## Q7", "**Stage 1**"); one that says a value ("**x = 3**",
    "**25 m**") is a statement."""
    return (
        bool(_HEADING.match(line))
        and not _VALUE_SIGN.search(line)
        and not _NUMBER_WITH_UNIT.search(line)
    )


def _states_a_result(
    lead: str,
    span: tuple[int, int],
    fenced: list[tuple[int, int]],
    worked: set[str],
    said: set[str],
) -> bool:
    """Prose stating a number the working never reaches ("**5 : 7**" over working that
    found 4 : 5) or what a card says ("**x = 3**" over a card of x = 3). A heading, a photo,
    a fence (a photo's query), a list, a part or a note stays, and so does a lead whose
    numbers are only the question's."""
    begin, end = span
    if any(begin < fence_end and fence_start < end for fence_start, fence_end in fenced):
        return False
    stripped = lead[begin:end].strip()
    if _a_heading(stripped) or _KEEP.match(stripped):
        return False
    if bool(_numbers(_ASIDE.sub(" ", stripped)) - worked):
        return True
    flat = _flat(stripped)
    return any(_says_whole(flat, statement) for statement in said)


def drop_guessed_lead(text: str) -> str:
    """``text`` without a short lead above its working that states a result: a number the
    working and its card never reach, or one a card shows."""
    given = _GIVEN.search(text)
    if given is None:
        return text
    if not any(
        fence.lang == "answer" and fence.start > given.start() for fence in iter_fences(text)
    ):
        return text
    # A Given inside a fence (an example in code) is not the reply's.
    if line_fences(text)[text.count("\n", 0, given.start())] is not None:
        return text
    lead = text[: given.start()]
    if len(lead.split()) > _MOST_WORDS or not lead.strip():
        return text
    fenced = [(fence.start, fence.end) for fence in iter_fences(lead)]
    spans = _paragraphs(lead)
    rest = text[given.start() :]
    worked = _numbers(rest) | {number.replace(",", "") for number in _NUMBER.findall(rest)}
    said = _card_statements(rest)
    kept = [span for span in spans if not _states_a_result(lead, span, fenced, worked, said)]
    if len(kept) == len(spans):
        return text
    head = "\n\n".join(lead[begin:end].strip("\n") for begin, end in kept)
    return f"{head}\n\n{text[given.start() :]}" if head else text[given.start() :]


# A restatement is short: one sentence or a few.
_TAIL_MOST_WORDS = 50
_TAIL_MOST_SENTENCES = 3
_SENTENCE_END = re.compile(r"[.!?](?:\s|$)")
# Not a sentence: a heading, a list, a table, a quote or a picture (a fence is a piece of
# its own, ``_tail_pieces``).
_NOT_PROSE = re.compile(r"^\s*(?:#|[-*+]\s|\d+[.)]\s|\||>|!\[|\[Image:)")
_LETTERS = re.compile(r"[^\W\d_]{2,}")
_TEX_COMMAND = re.compile(r"\\[A-Za-z]+")
# The words that join a restatement and say nothing of their own.
_GLUE = frozenset(
    "the a an is are was were be and or of for to in on at by with its it their this that "
    "so thus therefore hence which has have then both each while whereas respectively "
    "approximately about roughly equal equals due we get our final".split()
)


def _words(text: str) -> set[str]:
    return {word.lower() for word in _LETTERS.findall(_TEX_COMMAND.sub(" ", text))}


def _card_numbers(text: str) -> set[str]:
    """The numbers the answer cards show."""
    found: set[str] = set()
    for fence in iter_fences(text):
        if fence.lang in ANSWER_FENCE_LANGS:
            body = text[fence.body_start : fence.body_end].replace(UNCHECKED_ANSWER_MARKER, "")
            found |= _numbers(body)
    return found


def _restates(paragraph: str, shown: set[str], known: set[str]) -> bool:
    """A short sentence or few stating only numbers the cards show (``shown``), in words
    the reply or the question already holds (``known``)."""
    text = paragraph.strip()
    if not text or _NOT_PROSE.match(text):
        return False
    if len(text.split()) > _TAIL_MOST_WORDS or len(_SENTENCE_END.findall(text)) > (
        _TAIL_MOST_SENTENCES
    ):
        return False
    numbers = _numbers(text)
    return bool(numbers) and numbers <= shown and _words(text) - _GLUE <= known


def _tail_pieces(tail: str) -> list[tuple[str, bool]]:
    """The text after the last card in pieces, each with whether it is prose: a fence is
    one piece, and the prose between fences is a piece per paragraph."""
    pieces: list[tuple[str, bool]] = []
    cursor = 0
    for fence in [*iter_fences(tail), None]:
        stop = len(tail) if fence is None else fence.start
        prose = tail[cursor:stop]
        pieces += [(prose[begin:end].strip("\n"), True) for begin, end in _paragraphs(prose)]
        if fence is not None:
            pieces.append((tail[fence.start : fence.end].strip("\n"), False))
            cursor = fence.end
    return pieces


def drop_restated_tail(text: str, question: str = "") -> str:
    """``text`` without a short paragraph after its last answer card that only says again
    what the cards show (module docstring). ``question``: the user's message, whose words
    (the car, due East) a restatement may use."""
    cards = [fence for fence in iter_fences(text) if fence.lang in ANSWER_FENCE_LANGS]
    if not cards or not cards[-1].closed:
        return text
    head, tail = text[: cards[-1].end].rstrip(), text[cards[-1].end :]
    shown = _card_numbers(head)
    known = _words(head) | _words(question)
    pieces = _tail_pieces(tail)
    kept = [piece for piece, prose in pieces if not (prose and _restates(piece, shown, known))]
    if len(kept) == len(pieces):
        return text
    return "\n\n".join([head, *kept]) + ("\n" if text.endswith("\n") else "")
