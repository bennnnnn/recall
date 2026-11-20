"""One quantity asked at several places: each place read alone, by its own law.

"Work out the tension in the rope at the bottom, top and halfway between the bottom and top
of the circle" got the bottom's 104 N with a check mark, and nothing else (the owner's chat,
2026-11-20): the bottom's law read its cue, "at the bottom", and the other two places in the
list went unread. Where a body is changes the answer only through a law written for that
place (its cue: "at the bottom", "highest point", "level with the centre"), so a list of
places that holds one of them asks one question per place:

- the list is read off the asking sentence: a place after "at", "on" or "in", and every
  place joined to it by commas and a last "and" or "or" ("at the bottom, top and halfway";
  "at the bottom and at the top"), each one named for a place, never a quantity ("the
  tension in the string and the speed at the top" asks two things, ``parts``);
- each place is the question again with the list replaced by that place alone, read and
  solved as any question is; every place's law must be one cued by that place, each a
  different law. One that no law answers leaves the question to the model: its places are
  counted as asks (``parts.asks_count``), so no single place's card stands for them all.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from functools import lru_cache

from app.core.config import Settings
from app.modules.physics.ask import QUANTITY, SENTENCE
from app.modules.physics.block import build_verified_physics_block
from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.numbers import normalize_physics_units
from app.modules.physics.split_parts import joined_parts, part_working
from app.services.law_binding.ask import ASK_VERBS
from app.services.law_binding.words import word_pattern
from app.services.solving import PhysicsPartWorking, VerifiedPhysicsBlock

logger = logging.getLogger(__name__)

# Where a place is said: "at the bottom", "on its highest point", "in the middle".
_LEAD = re.compile(r"\b(?P<at>at|on|in)[ \t]+(?:(?:the|its)[ \t]+)?", re.IGNORECASE)
_DETERMINER = re.compile(r"(?:the|its)[ \t]", re.IGNORECASE)
# Between two places of one list: a comma, a last "and" or "or" (with or without one).
_SEPARATOR = re.compile(
    r"[ \t]*,[ \t]*(?:(?P<comma_last>and|or)[ \t]+)?|[ \t]+(?P<last>and|or)[ \t]+",
    re.IGNORECASE,
)
# Where one place of a list ends: its comma, or the "and" or "or" after it.
_PLACE_END = re.compile(r",|[ \t](?:and|or)[ \t]", re.IGNORECASE)
_MAX_PLACES = 4
# A place is a few words; a longer run is a clause, not a place.
_MAX_PLACE_WORDS = 10


@dataclass(frozen=True)
class _PlaceList:
    start: int
    end: int
    # The list's "at the", and its "at" alone, for a place written "the top".
    lead: str
    at: str
    places: tuple[str, ...]


def _asking(sentence: str) -> bool:
    return sentence.rstrip().endswith("?") or ASK_VERBS.search(sentence) is not None


@lru_cache(maxsize=1)
def _place_cues() -> tuple[re.Pattern[str], ...]:
    """Every cue a catalog law is written for a situation with."""
    from app.modules.physics.catalog import CATALOG

    cues = {
        cue
        for spec in CATALOG.values()
        if spec.binding is not None
        for cue in spec.binding.cues
        if not cue.startswith("re:")
    }
    return tuple(word_pattern(cue) for cue in sorted(cues))


def _cued(place: str) -> bool:
    lower = place.lower()
    return any(cue.search(lower) for cue in _place_cues())


def _placed(found: _PlaceList, place: str) -> str:
    """The place with the list's "at the" when it was written without one: "top" is "at the
    top", "the lowest point" "at the lowest point"."""
    if _LEAD.match(place):
        return place
    return f"{found.at} {place}" if _DETERMINER.match(place) else f"{found.lead}{place}"


def _read_list(sentence: str, lead: re.Match[str]) -> _PlaceList | None:
    """The places joined from this lead on, when they make a list ending in "and"/"or"."""
    places: list[str] = []
    at = lead.end()
    while len(places) <= _MAX_PLACES:
        end = _PLACE_END.search(sentence, at)
        place_end = len(sentence) if end is None else end.start()
        places.append(sentence[at:place_end].strip())
        separator = _SEPARATOR.match(sentence, place_end)
        if separator is None:
            return None  # no "and" or "or": a clause after a comma, not a list
        at = separator.end()
        if separator.group("comma_last") or separator.group("last"):
            break
    else:
        return None
    # The last place runs to the next comma or the sentence's end, its stop left out.
    comma = sentence.find(",", at)
    last = sentence[at : len(sentence) if comma < 0 else comma].rstrip(" \t\n.?!;:")
    places.append(last.strip())
    last_end = at + len(last)
    return _PlaceList(lead.start(), last_end, lead.group(0), lead.group("at"), tuple(places))


def _a_place(place: str) -> bool:
    words = place.split()
    return 0 < len(words) <= _MAX_PLACE_WORDS and QUANTITY.search(place) is None


def _place_list(sentence: str) -> _PlaceList | None:
    """The first list of places the sentence asks about, one of them a law's place."""
    for lead in _LEAD.finditer(sentence):
        found = _read_list(sentence, lead)
        # "in the rope at the bottom, top …": the list starts at the place nearest it.
        if found is None or _LEAD.search(found.places[0]) is not None:
            continue
        placed = [_placed(found, place) for place in found.places]
        if all(_a_place(place) for place in found.places) and any(map(_cued, placed)):
            return found
    return None


def _asked_list(text: str) -> tuple[int, _PlaceList] | None:
    """The asked list of places, and where its sentence starts in ``text``."""
    for match in SENTENCE.finditer(text):
        sentence = match.group()
        if _asking(sentence) and (found := _place_list(sentence)) is not None:
            return match.start(), found
    return None


def asked_places(text: str) -> int:
    """How many places one asked quantity is asked at; 0 when no list of places is."""
    found = _asked_list(text)
    return 0 if found is None else len(found[1].places)


def _law_of_the_place(block: VerifiedPhysicsBlock, place: str) -> bool:
    """The reading's law is written for this place: one of its cues is the place's."""
    from app.modules.physics.catalog import formula_spec

    intent = block.physics_intent
    spec = formula_spec((intent and intent.physics_op) or "")
    if spec is None or spec.binding is None:
        return False
    lower = place.lower()
    return any(word_pattern(cue).search(lower) for cue in spec.binding.cues)


def _solved_at(place: str, reading: str, settings: Settings) -> VerifiedPhysicsBlock | None:
    """The question asked at this place alone, solved by a law written for the place."""
    intent = extract_physics_intent(reading)
    if intent is None:
        return None
    try:
        block = build_verified_physics_block(intent, settings)
    except Exception:
        logger.info("physics place block declined: %s", intent.physics_op, exc_info=True)
        return None
    return block if block is not None and _law_of_the_place(block, place) else None


def _asked_noun(working: PhysicsPartWorking) -> str:
    """What the part's law finds, as a heading: "Tension"."""
    from app.modules.physics.catalog import formula_spec
    from app.modules.physics.law_nouns import result_name

    spec = formula_spec(working.op)
    noun = None if spec is None else result_name(spec)
    return working.title if not noun else noun[:1].upper() + noun[1:]


def solve_at_places(text: str, settings: Settings) -> VerifiedPhysicsBlock | None:
    """One verified block answering the asked quantity at every listed place, or None."""
    question = normalize_physics_units(text)
    asked = _asked_list(question)
    if asked is None:
        return None
    offset, found = asked
    start, end = offset + found.start, offset + found.end
    blocks: list[VerifiedPhysicsBlock] = []
    workings: list[PhysicsPartWorking] = []
    for place in (_placed(found, place) for place in found.places):
        reading = f"{question[:start]}{place}{question[end:]}"
        block = _solved_at(place, reading, settings)
        working = None if block is None else part_working(block, place, reading)
        if block is None or working is None:
            return None
        blocks.append(block)
        workings.append(replace(working, title=f"{_asked_noun(working)} {place}"))
    if len({working.op for working in workings}) < len(workings):
        return None  # one law for two places: no place changed the answer it read
    return joined_parts(blocks, workings)
