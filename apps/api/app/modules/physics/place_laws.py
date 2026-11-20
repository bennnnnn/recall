"""Laws of one situation at its places: a vertical circle's bottom, top and side.

A situation whose answer depends on where the body is has one law per place, of one law
name and one ask, each cued by its place and each ruling the others' places out (its
excludes hold a cue of every other): T = m(v²/r + g) at the bottom, m(v²/r - g) at the top,
mv²/r level with the centre. Their cues are the places the catalog knows (``place_parts``).

Each law takes the speed at its own place. A question that names another place of the
circle ("it passes the bottom at 8 m/s … the tension at the top") states the speed there,
and the top's law filled with it gave 27.1 N for 7.5 N, verified (review of the place
fix, 2026-11-20). So a place's law holds only when the question names no other place, or
says the speed is steady (``law_refusals``).
"""

from __future__ import annotations

import re
from collections import defaultdict
from functools import lru_cache

from app.services.law_binding.spec import FormulaSpec
from app.services.law_binding.words import word_pattern

# A place's preposition and article: "at the bottom" names the bottom.
LEAD = re.compile(r"\b(?P<at>at|on|in)[ \t]+(?:(?:the|its)[ \t]+)?", re.IGNORECASE)


@lru_cache(maxsize=1)
def _siblings() -> dict[str, tuple[FormulaSpec, ...]]:
    """Each place law's id, and the laws of the situation's other places."""
    from app.modules.physics.catalog import CATALOG

    families: dict[tuple[str, tuple[str, ...]], list[FormulaSpec]] = defaultdict(list)
    for spec in CATALOG.values():
        if spec.binding is not None and spec.binding.cues:
            families[(spec.law_name, spec.binding.asks)].append(spec)
    found: dict[str, tuple[FormulaSpec, ...]] = {}
    for laws in families.values():
        if len(laws) > 1 and all(_rules_out(one, other) for one in laws for other in laws):
            for law in laws:
                found[law.id] = tuple(other for other in laws if other is not law)
    return found


def _rules_out(one: FormulaSpec, other: FormulaSpec) -> bool:
    if one is other or one.binding is None or other.binding is None:
        return one is other
    return any(cue in one.binding.excludes for cue in other.binding.cues)


@lru_cache(maxsize=1)
def place_cues() -> tuple[re.Pattern[str], ...]:
    """Every place a place law is cued by."""
    cues = {cue for law_id in _siblings() for cue in _cues_of(law_id) if not cue.startswith("re:")}
    return tuple(word_pattern(cue) for cue in sorted(cues))


def _cues_of(law_id: str) -> tuple[str, ...]:
    from app.modules.physics.catalog import formula_spec

    spec = formula_spec(law_id)
    return () if spec is None or spec.binding is None else spec.binding.cues


def _place_word(cue: str) -> re.Pattern[str]:
    """The place a cue names, said without its "at the": "at the bottom" is "bottom"."""
    lead = LEAD.match(cue)
    return word_pattern(cue[lead.end() :] if lead is not None else cue)


def names_another_place(spec: FormulaSpec, lower: str) -> bool:
    """The question names a place of the situation other than this law's own."""
    return any(
        _place_word(cue).search(lower) is not None
        for other in _siblings().get(spec.id, ())
        if other.binding is not None
        for cue in other.binding.cues
    )
