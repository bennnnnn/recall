"""Words by language, kept as data (``data/*.json``): units, asks and signs.

The translation check reads the original question with these tables, never with the
model: a unit word becomes its unit ("120 ሜትር" is 120 m), a quantity named beside an ask
word is what the question asks, and "bajo cero" makes a temperature negative. A word the
tables do not hold is read as no unit and no ask, which the check then holds the English
to as well.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

_DATA = Path(__file__).with_name("data")
# Languages whose words take attached prefixes and suffixes ("የመኪናው ፍጥነት", "سرعته",
# "скорости"): a table word is matched inside a longer word there.
_ATTACHED_PREFIX = frozenset({"am", "ar"})
_ATTACHED_SUFFIX = frozenset({"am", "ar", "ru", "tr"})
# A word this long takes attached prefixes and suffixes; a shorter one stands alone.
_ATTACHED_LENGTH = 3
_SENTENCE_END = re.compile(r"[.!?؟።፧;\u0964\u0965\n](?=\s|$)")
# A digit of any script, Ethiopic numerals among them.
_AFTER_NUMBER = re.compile(r"[\d\u1369-\u137c]\s*\Z")


@dataclass(frozen=True, slots=True)
class _Named:
    start: int
    end: int
    kinds: frozenset[str]
    unit: bool


# How far from an ask word its quantity may be named.
_ASK_REACH = 60


@cache
def _table(name: str) -> dict[str, Any]:
    """One data file, its notes ("_doc") left out. Its shape is the file's own."""
    loaded: dict[str, Any] = json.loads((_DATA / f"{name}.json").read_text(encoding="utf-8"))
    return {key: value for key, value in loaded.items() if not key.startswith("_")}


# An Ethiopic syllable is its consonant and one of eight vowels: a suffix changes the last
# one's vowel ("ፍጥነት", speed; "ፍጥነቱ", its speed).
_ETHIOPIC_SYLLABLES = range(0x1200, 0x1358)


def _written(word: str) -> str:
    """``word`` as a pattern: its last Ethiopic syllable with any vowel, in a word of three
    or more ("ሞል", mole, is not the start of "ሞለኪውል", molecule)."""
    last = ord(word[-1]) if len(word) >= _ATTACHED_LENGTH else 0
    if last not in _ETHIOPIC_SYLLABLES:
        return re.escape(word)
    first = 0x1200 + (last - 0x1200) // 8 * 8
    return re.escape(word[:-1]) + f"[{chr(first)}-{chr(first + 7)}]"


def _alternation(words: list[str]) -> str:
    return "|".join(_written(word) for word in sorted(set(words), key=len, reverse=True))


def number_words(section: str, language: str) -> Any:
    """One section of ``numbers.json`` for one language (``{}`` or ``[]`` when it has none)."""
    found = _table("numbers").get(section, {}).get(language)
    if found is not None:
        return found
    return {} if section in {"scales", "fractions"} else []


@cache
def below_zero_words(language: str) -> re.Pattern[str]:
    """Words right after a value (up to two more words of its unit) that make it negative."""
    table = _table("below_zero")
    words = [*table.get("en", []), *table.get(language, [])]
    return re.compile(rf"\A\s*(?:\S+\s+){{0,2}}?(?:{_alternation(words)})(?!\w)", re.IGNORECASE)


@cache
def _unit_words(language: str) -> tuple[re.Pattern[str], dict[str, str]]:
    meaning: dict[str, str] = {}
    for unit, by_language in _table("units").items():
        entry: dict[str, list[str]] = by_language
        for word in [*entry.get("*", []), *entry.get(language, [])]:
            meaning[word.lower()] = unit
    attached = language in _ATTACHED_SUFFIX
    words = sorted(meaning, key=len, reverse=True)
    # A short unit ("g", "ሜ", "م", "ሞል") is a word of its own, never the start of one.
    ends = r"(?![\w'\u2019])"
    groups = "|".join(
        f"({_written(word)})" + ("" if attached and len(word) >= _ATTACHED_LENGTH else ends)
        for word in words
    )
    # A unit starts a word ("م", metre, is not the start of "من"); a digit may come before
    # it ("15٪", "5km").
    return re.compile(rf"\s?(?<![^\W\d_])(?:{groups})", re.IGNORECASE), dict(
        zip(map(str, range(1, len(words) + 1)), (meaning[word] for word in words), strict=True)
    )


@cache
def _unit_kinds() -> dict[str, str]:
    return {unit: str(entry["kind"]) for unit, entry in _table("units").items()}


def unit_word_at(text: str, end: int, language: str) -> tuple[str, int] | None:
    """The unit a word right after ``end`` names, as Pint writes it, and where it ends."""
    pattern, meaning = _unit_words(language)
    found = pattern.match(text, end)
    if found is None or found.lastindex is None:
        return None
    end = found.end()
    if language in _ATTACHED_SUFFIX:
        # The rest of an attached word is the unit's too ("ሜትሮች", metres).
        while end < len(text) and text[end].isalpha():
            end += 1
    return meaning[str(found.lastindex)], end


def _bounded(phrases: str, language: str) -> str:
    affixes = _affixes(language)
    if affixes is not None:
        # A word with the prefixes and suffixes its language attaches ("سرعته", its speed).
        prefixes, suffixes = (
            _alternation(affixes.get(key, [])) for key in ("prefixes", "suffixes")
        )
        return rf"(?<!\w)(?:{prefixes})?(?:{phrases})(?:{suffixes})?(?!\w)"
    before = "" if language in _ATTACHED_PREFIX else r"(?<!\w)"
    after = "" if language in _ATTACHED_SUFFIX else r"(?!\w)"
    return rf"{before}(?:{phrases}){after}"


def _affixes(language: str) -> dict[str, Any] | None:
    table = _table("asks").get(language)
    return table.get("affixes") if isinstance(table, dict) else None


def _with_endings(phrase: str, language: str) -> str:
    """``phrase`` as a pattern, its last letter in any form a suffix gives it ("طاقة",
    energy; "طاقته", its energy)."""
    endings = (_affixes(language) or {}).get("endings", {})
    last = phrase[-1:]
    if last in endings:
        return re.escape(phrase[:-1]) + f"[{re.escape(last + endings[last])}]"
    return _written(phrase)


@cache
def _asks(
    language: str,
) -> tuple[re.Pattern[str], list[tuple[re.Pattern[str], frozenset[str]]]]:
    table = _table("asks").get(language)
    if not isinstance(table, dict):
        raise KeyError(language)
    kinds: dict[str, frozenset[str]] = {}
    for named, phrases in table["classes"].items():
        for phrase in phrases:
            kinds[phrase.lower()] = kinds.get(phrase.lower(), frozenset()) | frozenset(
                named.split("|")
            )
    patterns = {_with_endings(phrase, language): phrase for phrase in kinds}
    marker_end = "" if language == "am" else r"(?!\w)"
    markers = re.compile(rf"(?<!\w)(?:{_alternation(table['markers'])}){marker_end}")
    named = [
        (re.compile(_bounded(pattern, language)), kinds[phrase])
        for pattern, phrase in sorted(patterns.items(), key=lambda item: -len(item[1]))
    ]
    return markers, named


# Arabic's short vowels and its stretching mark: a question may write them or not.
_ARABIC_MARKS = re.compile("[\u064b-\u0652\u0670\u0640]")
_CLAUSE_END = re.compile(r"[,\u060c\u1363](?=\s)")
_QUESTION_MARK = re.compile("[?\u061f\u1367]")
# A word for a quantity that names no kind: "amount", "كمية".
_UNNAMED = frozenset({"unnamed"})
# Languages that put a phrase's head last: an ask with no ask word names its kind last.
_HEAD_LAST = frozenset({"am", "hi", "tr"})
# How far from the named quantity its qualifier may be: "rapidez media", "final speed".
_QUALIFIER_REACH = 16
# A unit this close after an ask word is what it asks: "how many grams", "ስንት ግራም".
_UNIT_ASK_REACH = 14


def _named(lower: str, language: str, marks: list[tuple[int, int]]) -> list[_Named]:
    """Every quantity the text names: a kind's word, or a unit not written after a number."""
    _, patterns = _asks(language)
    named: list[_Named] = []

    def free(start: int, end: int, length: int) -> bool:
        taken = any(start < item.end and item.start < end for item in named)
        # "Work out" asks; its "work" names no energy.
        inside = any(s <= start and end <= e and e - s >= length for s, e in marks)
        return not taken and not inside and _AFTER_NUMBER.search(lower, 0, start) is None

    for pattern, kinds in patterns:  # longest first: "masse volumique" before "masse"
        for found in pattern.finditer(lower):
            if free(*found.span(), len(found.group(0))):
                named.append(_Named(found.start(), found.end(), kinds, unit=False))
    units, meaning = _unit_words(language)
    prefixed = language in _ATTACHED_PREFIX
    for found in units.finditer(lower):
        start, end = found.start() + (1 if found.group(0)[:1].isspace() else 0), found.end()
        before, after = lower[start - 1 : start], lower[end : end + 1]
        # A unit stands as a word ("በዲግሪ", in degrees, may take a prefix); "\\sec(" is maths.
        alone = not before.isalpha() or (prefixed and end - start >= _ATTACHED_LENGTH)
        if found.lastindex is None or not alone or before == "\\" or after == "(":
            continue
        if free(start, end, end - start):
            kind = _unit_kinds()[meaning[str(found.lastindex)]]
            named.append(_Named(start, end, frozenset({kind}), unit=True))
    return named


def _span(edges: list[int], start: int, end: int) -> tuple[int, int]:
    return max(edge for edge in edges if edge <= start), min(edge for edge in edges if edge >= end)


@dataclass(frozen=True, slots=True)
class Asked:
    """One ask: the kinds of quantity it could be, and how it is qualified ("average",
    "final")."""

    kinds: frozenset[str]
    qualifiers: frozenset[str]


@cache
def _qualifiers(language: str) -> list[tuple[re.Pattern[str], str]]:
    table = _table("asks").get(language)
    named = table.get("qualifiers", {}) if isinstance(table, dict) else {}
    return [
        (re.compile(_bounded(_alternation(words), language)), name) for name, words in named.items()
    ]


def _qualified(lower: str, item: _Named, clause: tuple[int, int], language: str) -> Asked:
    """The ask named by ``item`` with the qualifiers written beside it in its clause."""
    lo, hi = (
        max(clause[0], item.start - _QUALIFIER_REACH),
        min(clause[1], item.end + _QUALIFIER_REACH),
    )
    found = {
        name for pattern, name in _qualifiers(language) if pattern.search(lower, lo, hi) is not None
    }
    return Asked(item.kinds, frozenset(found))


def asked_kinds(text: str, language: str) -> tuple[Asked, ...] | None:
    """The kinds of quantity each ask could be; None for a language with no table.

    For each ask word: a unit right after it ("how many grams"), else the quantity named
    nearest it in its clause, else in its sentence. A question with no ask word ("área de
    un círculo con radio 7 cm", "..., corriente total?") asks the quantity at its head in
    its question clause (or first clause): the first named, or the last in a language that
    puts the head last ("7 cm त्रिज्या वाले वृत्त का क्षेत्रफल").
    """
    try:
        markers, _ = _asks(language)
    except KeyError:
        return None
    lower = _ARABIC_MARKS.sub("", text.lower())
    sentences = [0, *(found.end() for found in _SENTENCE_END.finditer(lower)), len(lower)]
    clauses = sorted({*sentences, *(found.end() for found in _CLAUSE_END.finditer(lower))})
    # An ask word after a number, or before a "/", is a unit: "18 كم/س" is 18 km/h.
    marks = [
        found.span()
        for found in markers.finditer(lower)
        if _AFTER_NUMBER.search(lower, 0, found.start()) is None
        and not lower.startswith("/", found.end())
    ]
    named = _named(lower, language, marks)
    if not marks:
        asked = _QUESTION_MARK.search(lower)
        clause = _span(clauses, asked.start(), asked.start()) if asked else (0, clauses[1])
        inside = sorted(
            (item for item in named if clause[0] <= item.start < clause[1]),
            key=lambda item: item.start,
        )
        if not inside:
            return ()
        return (_qualified(lower, inside[-1 if language in _HEAD_LAST else 0], clause, language),)
    found: list[Asked] = []
    for start, end in marks:
        clause_end = _span(clauses, start, end)[1]
        after = [
            item
            for item in named
            if item.unit and 0 <= item.start - end <= _UNIT_ASK_REACH and item.end <= clause_end
        ]
        if after:
            unit = min(after, key=lambda item: item.start)
            found.append(_qualified(lower, unit, _span(clauses, start, end), language))
            continue
        for edges in (clauses, sentences):
            lo, hi = _span(edges, start, end)
            near = [
                (max(item.start - end, start - item.end, 0), item)
                for item in named
                if lo <= item.start and item.end <= hi
            ]
            near = [(gap, item) for gap, item in near if gap <= _ASK_REACH]
            if near:
                # "Amount" names no kind; "the amount of charge" names charge.
                nearest = min(near, key=lambda pair: (pair[1].kinds == _UNNAMED, pair[0]))
                found.append(_qualified(lower, nearest[1], (lo, hi), language))
                break
    return tuple(found)
