"""Every number a question states is read by its verified card, or the card is dropped.

A card that ignores a stated number answers another question: "twenty 60 W bulbs" answered
one bulb's energy, "both of the resistors are 10 Ω" one resistor's current, "the total mass
of 2 moles of NaCl and 3 moles of water" the salt alone (2026-10-31, reviews of #2172).
The gate reads the question's numbers and counts and asks each to be in what the solve
read: its block, its working and its intent. A count is read when its number is, when a
value is read that many times (R1 = R2 = 10 Ω for "two 10 Ω resistors"), or when that many
values in one unit are ("at 20 m/s and 10 m/s" for "two cars"). A vague count ("several",
"many") is never read. Exercise and page numbers and years are labels. A dropped card is
no card: the model answers, as for any question no solver reads.

An experiment behind ``verified_numbers_gate`` ("off"; "counts" reads only counts, "all"
every number too); measured before it is on.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Any

from app.core.config import Settings
from app.services.number_text import NUMBER_WORDS
from app.services.solving import VerifiedSolveBlock

# One number as written, not a name's index ("R1", "H2O") or a power ("m/s^2").
# "s^-1" is a unit's power, not -1 or 1.
_NUMBER = re.compile(
    r"(?<![A-Za-z\d.,^_])(?<!\^-)-?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"
)
_TIMES_TEN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:[x\u00d7*]\s*10\s*(?:\^|\*\*)\s*\(?|e)(-?\d+)\)?", re.IGNORECASE
)
# What a solve wrote may raise a number to a power ("3^4", "3**4"): its digits are read.
_READ_NUMBER = re.compile(
    r"(?<![A-Za-z\d.,_])-?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?"
)
_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
_SUPERSCRIPT_RUN = re.compile("[⁰¹²³⁴-⁹⁻]+")
# A count that names how many items: the words for 2 to 20 and a few more.
_COUNTS = {word: value for word, value in NUMBER_WORDS.items() if 2 <= value <= 20}
_COUNTS |= {"both": 2, "pair": 2, "couple": 2, "twice": 2, "dozen": 12, "score": 20}
# A count, the items it counts and, when written inside the phrase, the value each has:
# "two resistors", "both of my phones", "twenty 60 W bulbs", "3 identical 9 Ω resistors".
_COUNT_RE = re.compile(
    rf"(?<![\d.,^])(?<!\^-)\b({'|'.join(sorted(_COUNTS, key=len, reverse=True))}|[2-9]|1\d|20)\b"
    r"\s+(?:(?:identical|equal|similar|of\s+(?:the|my|these|those))\s+)?"
    r"(?P<inside>[\d.]+\s*\S+\s+)?(?P<noun>[a-z]{2,}[^s\W]s)\b",
    re.IGNORECASE,
)
# Words that may stand between counted items and the value each has ("both of my phones
# charge at 20 W", "the bulbs are rated 60 W"); any other word ("is connected across")
# makes the value another thing's.
_ITEM_LINKS = frozenset(
    "are is were was each have has had with of a an at rated charge charges run runs use uses "
    "draw draws pull pulls push pushes weigh weighs carry carries hold holds deliver delivers "
    "produce produces provide provides power resistance mass weight force voltage emf "
    "capacitance charge rating".split()
)
_CLAUSE_END = re.compile(r"[.,;:?!](?=\s|$)")


def _count_value(written: str) -> int:
    return int(written) if written.isdigit() else _COUNTS[written.lower()]


# "Several 60 W bulbs", "many 2 kg bricks": a count no solve can read.
# The items a vague count counts: "several 60 W bulbs".
_COUNT_AFTER_VAGUE = re.compile(
    r"(?P<inside>[\d.]+\s*\S+\s+)?(?P<noun>[a-z]{2,}[^s\W]s)\b", re.IGNORECASE
)
_VAGUE = re.compile(
    r"(?<!how\s)(?<!as\s)\b(?:several|many|numerous|multiple|a\s+few|some|various)\s+"
    r"(?=\d|[a-z]+s\b)",
    re.IGNORECASE,
)
# "Question 3", "Exercise 2.15", "Q1", a leading "4." and a year are labels, not values.
_LABEL = re.compile(
    r"\b(?:question|exercise|problem|example|part|page|chapter|section|step|figure|fig|"
    r"table|q|ex)\.?\s*#?\s*(\d+(?:\.\d+)*)[a-z]?\b",
    re.IGNORECASE,
)
_LIST_NUMBER = re.compile(r"\A\s*\(?(\d{1,3})[.)]\s")
# "Iodine-131", "carbon-14", "s-1": a name's number or a unit's power.
_NAMED = re.compile(r"(?<=[A-Za-z]-)(\d+)")
# "I got 48 A. Is that right?": a student's claim is checked, not read.
_CLAIM = re.compile(
    r"\b(?:i\s+got|i\s+get|my\s+answer\s+(?:is|was)|i\s+calculated|i\s+think\s+it'?s)"
    r"(?:\s+[a-z]+){0,4}?\s+(-?[\d.,]+(?:\s*[x\u00d7*]\s*10\^-?\d+)?)",
    re.IGNORECASE,
)
# "1/16": a fraction may be read as its value.
_FRACTION = re.compile(r"(?<![\d.,/])(\d+)\s*/\s*(\d+)(?![\d.,/])")
# "CuSO4·5H2O", "2H2O": a number glued to a formula is the formula's.
_IN_FORMULA = re.compile(r"(\d+)(?=[A-Z][a-z]?\d*)")
# "[A]0", "(x)2": an index written onto a bracket.
_INDEX = re.compile(r"(?<=[\])])(\d+)")
_YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)\b(?!\s*(?:[a-zA-Z%°Ωµ]|/))")
_UNIT_AFTER = re.compile(r"\s*([^\s\d,.;:!?()]+)")


def _plain(text: str) -> str:
    return _SUPERSCRIPT_RUN.sub(lambda run: "^" + run.group(0).translate(_SUPERSCRIPT), text)


def _values(text: str) -> list[float]:
    """Every value ``text`` writes, a power of ten as one."""
    plain = _plain(text)
    found = [float(m.group(1)) * 10 ** int(m.group(2)) for m in _TIMES_TEN.finditer(plain)]
    for match in _READ_NUMBER.finditer(_TIMES_TEN.sub(" ", plain)):
        try:
            found.append(float(match.group(0).replace(",", "")))
        except ValueError:
            continue
    return found


def _read_text(question: str, verified: VerifiedSolveBlock) -> str:
    """What the solve read: its intent's inputs, never its result (a "2 m/s²" answer is no
    reading of "two horses"). A maths block keeps no intent, so the question's maths
    intent is read again; a block with no intent at all is read without its answer."""
    parts: list[str] = []
    physics = getattr(verified, "physics_intent", None)
    if physics is not None:
        parts.append(json.dumps(physics.physics_params or {}))
    chemistry: Any = getattr(verified, "intent", None)
    if chemistry is not None:
        # Every input field of the read; its result lives apart, on the block.
        parts.append(json.dumps(chemistry.model_dump(mode="json", exclude_none=True)))
    if verified.subject == "math":
        from app.modules.math.tools.extract import extract_math_intent

        intent = extract_math_intent(question)
        if intent is not None:
            parts.append(json.dumps(intent.model_dump(mode="json", exclude_none=True)))
    for part in getattr(verified, "physics_parts", ()):
        parts.extend(part.substitutions)
    if parts:
        return "\n".join(parts)
    text = verified.text
    for answer in (verified.canonical_answer, verified.display_answer):
        if answer:
            text = text.replace(answer, " ")
    return text


# A value may be read at another metric prefix ("500 mΩ" as 0.5 Ω), and with a sign
# its law gives it (a throw downward at -10 m/s).
_PREFIX_SCALES = tuple(10.0**power for power in range(-12, 13, 3))


def _read(value: float, read: list[float]) -> bool:
    return any(
        math.isclose(abs(value) * scale, abs(other), rel_tol=1e-6, abs_tol=1e-12)
        for other in read
        for scale in _PREFIX_SCALES
    )


def _label_spans(text: str) -> list[tuple[int, int]]:
    spans = [match.span(1) for match in _LABEL.finditer(text)]
    spans += [match.span(1) for match in _YEAR.finditer(text)]
    spans += [match.span(1) for match in _NAMED.finditer(text)]
    spans += [match.span(1) for match in _CLAIM.finditer(text)]
    spans += [match.span(1) for match in _INDEX.finditer(text)]
    spans += [match.span(1) for match in _IN_FORMULA.finditer(text)]
    listed = _LIST_NUMBER.match(text)
    if listed is not None:
        spans.append(listed.span(1))
    return spans


def _stated(plain: str, labels: list[tuple[int, int]]) -> list[tuple[str, float, int]]:
    """Each value the question states that is no label: (as written, value, its end)."""
    found: list[tuple[str, float, int]] = []
    powers = [match.span() for match in _TIMES_TEN.finditer(plain)]
    for match in _TIMES_TEN.finditer(plain):
        if not any(start <= match.start() < end for start, end in labels):
            value = float(match.group(1)) * 10 ** int(match.group(2))
            found.append((match.group(0), value, match.end()))
    for match in _NUMBER.finditer(plain):
        inside = [*labels, *powers]
        if any(start <= match.start() < end for start, end in inside):
            continue
        try:
            value = float(match.group(0).replace(",", ""))
        except ValueError:
            continue
        found.append((match.group(0), value, match.end()))
    return found


def _valued(text: str, match: re.Match[str]) -> bool:
    """Whether a count's items have a value each: written inside the phrase ("twenty 60 W
    bulbs"), said with "each" in the clause, or joined to the items by linking words only
    ("both of my phones charge at 20 W"). "A 12 V battery has two cells" counts parts
    whose value the question does not give each."""
    if match.group("inside"):
        return True
    ends = [found.start() for found in _CLAUSE_END.finditer(text, match.end())]
    clause = text[match.end() : ends[0] if ends else len(text)]
    value = _NUMBER.search(clause)
    if value is None:
        return False
    between = clause[: value.start()]
    if re.search(r"\beach\b", between, re.IGNORECASE):
        return True
    if re.match(r"\s*\S+\s+apart\b", clause[value.end() :], re.IGNORECASE):
        return False  # "two plates 2 cm apart": the gap between them
    return all(word in _ITEM_LINKS for word in re.findall(r"[a-z]+", between.lower()))


def _has_unit(text: str, start: int) -> bool:
    from app.modules.chemistry.given_units import CHEMISTRY_UNITS
    from app.modules.physics.givens import PHYSICS_UNITS

    digits = re.match(r"\d+", text[start:])
    end = start + (len(digits.group(0)) if digits else 0)
    return any(table.at(text, end) is not None for table in (PHYSICS_UNITS, CHEMISTRY_UNITS))


def _times_read(value: float, read: list[float]) -> int:
    """How many read values are ``value``, at any metric prefix."""
    return sum(
        1
        for other in read
        if any(
            math.isclose(abs(value) * scale, abs(other), rel_tol=1e-6, abs_tol=1e-12)
            for scale in _PREFIX_SCALES
        )
    )


def unaccounted(
    question: str, verified: VerifiedSolveBlock, *, counts_only: bool = False
) -> list[str]:
    """The numbers and counts ``question`` states that the verified solve did not read;
    with ``counts_only``, only its counts."""
    plain = _plain(question)
    read = _values(_read_text(question, verified))
    labels = _label_spans(plain)
    counts = [
        (match.start(1), match.group(1), _count_value(match.group(1)))
        for match in _COUNT_RE.finditer(plain)
        if _valued(plain, match)
    ]
    # "5 hours" is a value: a number with a unit is never a count.
    counts = [item for item in counts if not item[1].isdigit() or not _has_unit(plain, item[0])]
    count_starts = {start for start, _, _ in counts}
    missing: list[str] = []
    stated: list[tuple[float, str]] = []
    for written, value, end in _stated(plain, labels):
        if end - len(written) in count_starts:
            continue  # "2 resistors": a count, read as one below
        unit = _UNIT_AFTER.match(plain, end)
        stated.append((value, unit.group(1) if unit else ""))
        if not counts_only and not _read(value, read):
            missing.append(written)
    for fraction in _FRACTION.finditer(plain):
        top, bottom = float(fraction.group(1)), float(fraction.group(2))
        whole = bottom != 0 and _read(top / bottom, read)
        if counts_only or whole or (_read(top, read) and _read(bottom, read)):
            # "1/16 of a sample" read as 0.0625: both its numbers are read.
            missing = [word for word in missing if word not in fraction.groups()]
    missing += [
        match.group(0).strip()
        for match in _VAGUE.finditer(plain)
        if (counted := _COUNT_AFTER_VAGUE.match(plain, match.end())) is None
        or _valued(plain, counted)
    ]
    for _, written, count in counts:
        # Read when one stated value is read that many times ("R1 = R2 = 10 Ω"), when that
        # many read values share a unit ("at 20 m/s and 10 m/s"), or when the count itself
        # is read more often than the question writes its number ("seven notebooks"; not
        # "both phones ... for 2 hours").
        repeated = any(_times_read(value, read) >= count for value, _ in stated)
        per_unit = Counter(unit for value, unit in stated if unit and _read(value, read))
        written_too = sum(1 for value, _ in stated if math.isclose(value, count))
        itself = _times_read(float(count), read) > written_too
        if not (repeated or itself or any(n >= count for n in per_unit.values())):
            missing.append(written)
    return missing


def accounts_for_every_number(
    question: str, verified: VerifiedSolveBlock | None, *, counts_only: bool = False
) -> bool:
    """Whether the verified solve read every number and count the question states."""
    return verified is None or not unaccounted(question, verified, counts_only=counts_only)


def passes_gate(question: str, verified: VerifiedSolveBlock | None, settings: Settings) -> bool:
    """Whether a verified card stands under ``verified_numbers_gate``."""
    gate = settings.verified_numbers_gate
    if gate == "off":
        return True
    return accounts_for_every_number(question, verified, counts_only=gate == "counts")
