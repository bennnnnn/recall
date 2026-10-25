"""A molecule's shape asked in a student's words, read by a closed grammar.

Live failure (2026-10-25): "Why is water bent tho, co2 isnt" got no verified answer. The VSEPR
reader read only "shape of <FORMULA>", so water, lowercase "co2" and "why is … bent" were not
read, and the model answered alone. A shape question in words is now read when the whole line
is one of these phrases, its molecules named as ``species_words`` reads them (water, ammonia,
co2, CH4):

- "shape of X", "what is the molecular geometry of X", "what shape is X", "X shape";
- "why is X bent", "how come X is linear", "is X polar (or nonpolar)";
- "bond angle in X", "polarity of X";
- two molecules: "why is X bent tho, Y isnt", "why is X bent but Y linear", "compare the
  shapes of X and Y", "the shapes of X and Y".

Every molecule must have one central-atom Lewis structure (``lewis_structure``): oxygen gas,
ethanol or iron is not read. Anything else declines ("what shape is the earth", "the pipe is
bent", "is co2 bad", "co2 levels are rising"), and the model answers.
"""

from __future__ import annotations

import re

from app.modules.chemistry.lewis import lewis_structure
from app.modules.chemistry.schemas import ChemistryIntent
from app.modules.chemistry.species_words import substance_mentions, with_formulas

_LEAD = (
    r"(?:(?:ok(?:ay)?|so|and|but|also|wait|hey|hmm+|um+|q|question|chem(?:istry)?(?:\s+hw)?)"
    r"[\s,.:!?]+)*"
)
_TAIL = r"(?:[\s,]+(?:tho|though|pls|please|lol|then|exactly|again|anyway|btw))*\s*[?.!]*"
_ARTICLE = r"(?:(?:a|an|the)\s+)?"
_ADJECTIVE = (
    r"(?:bent|linear|polar|non-?\s?polar|tetrahedral|trigonal\s+(?:planar|pyramidal)|"
    r"pyramidal|v-?\s?shaped|planar|angular)"
)
_NOUN = r"(?:(?:molecular|electron(?:ic)?|vsepr)\s+)?(?:shape|geometry)"
_WHAT = r"(?:what(?:'s|s|\s+is|\s+are)?\s+)?(?:the\s+)?"
_WHY = r"(?:why|how\s+come)"
# "tho," "but" or a comma between the two molecules of a comparison.
_BETWEEN = r"(?:[\s,]+(?:but|tho|though|while|whereas|and|yet|when))*[\s,]+"
_NOT = r"(?:is\s*n[o'\u2019]?t|isnt|isn't|aint|ain't|is\s+not|not)"


def _molecule(name: str, substance: str) -> str:
    return rf"{_ARTICLE}(?P<{name}>{substance})(?:\s+molecules?)?"


def _phrases(substance: str) -> tuple[str, ...]:
    one, two = _molecule("one", substance), _molecule("two", substance)
    return (
        rf"{_WHAT}{_NOUN}\s+(?:of|for)\s+{one}",
        rf"what\s+(?:shape|geometry)\s+(?:is|does)\s+{one}(?:\s+have)?",
        rf"{_WHY}\s+(?:is|are)\s+{one}\s+{_ADJECTIVE}",
        rf"{_WHY}\s+{one}\s+is\s+{_ADJECTIVE}",
        rf"is\s+{one}\s+{_ADJECTIVE}(?:\s+or\s+{_ADJECTIVE})?",
        rf"{_WHAT}(?:bond\s+angles?|polarity)\s+(?:of|in|for)\s+{one}",
        rf"{one}\s+(?:shape|geometry|bond\s+angle|polarity)",
        rf"{_WHY}\s+(?:is|are)\s+{one}\s+{_ADJECTIVE}{_BETWEEN}{two}"
        rf"(?:\s+(?:{_NOT}|is\s+{_ADJECTIVE}|{_ADJECTIVE}))?",
        rf"compare\s+(?:the\s+)?(?:shapes?|geometr(?:y|ies)|bond\s+angles?)\s+(?:of\s+)?{one}"
        rf"\s+(?:and|&|with|to|vs\.?|versus)\s+{two}",
        rf"{_WHAT}(?:shapes?|geometr(?:y|ies)|bond\s+angles?)\s+of\s+{one}"
        rf"\s+(?:and|&|vs\.?|versus)\s+{two}",
    )


def shape_question(text: str) -> tuple[str, ...] | None:
    """The molecules (one or two, as formulas) whose shape the whole line asks; else None."""
    mentions = substance_mentions(text)
    if not mentions:
        return None
    formulas = sorted({mention.formula for mention in mentions}, key=len, reverse=True)
    line = with_formulas(text, mentions).strip()
    substance = "(?-i:" + "|".join(re.escape(formula) for formula in formulas) + ")"
    substance += r"(?![A-Za-z0-9])"
    for phrase in _phrases(substance):
        found = re.fullmatch(rf"{_LEAD}{phrase}{_TAIL}", line, re.IGNORECASE)
        if found is None:
            continue
        asked = tuple(
            dict.fromkeys(name for name in found.groupdict().values() if name is not None)
        )
        # The line names nothing else, and every molecule has one central atom to read.
        if set(asked) != {mention.formula for mention in mentions}:
            return None
        return asked if all(lewis_structure(formula) for formula in asked) else None
    return None


def extract_shape(text: str) -> ChemistryIntent | None:
    """A shape question in words: one molecule's VSEPR, or two compared ("H2O, CO2")."""
    asked = shape_question(text)
    if asked is None:
        return None
    return ChemistryIntent(kind="structure", chemistry_op="vsepr", formula=", ".join(asked))
