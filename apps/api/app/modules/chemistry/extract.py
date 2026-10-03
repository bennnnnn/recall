"""Conservative text-to-``ChemistryIntent`` extraction.

Each branch requires both a chemistry cue and the complete values needed by a
solver. Incomplete or ambiguous questions remain on the model path; verified
labels are never produced from guessed values.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.binding import bind_chemistry_intent
from app.modules.chemistry.registry import CHEMISTRY_EXTRACTORS, UNIT_AWARE_EXTRACTORS
from app.modules.chemistry.sig_figs import written_numbers
from app.services.number_text import read_scientific_numbers

_MAX_TEXT_LENGTH = 4000
logger = logging.getLogger(__name__)
# Units the labelled templates do not read: they would take "5 mM" as 5 M or kcal as kJ.
# A question written in one is read only by the readers that convert units (the
# Michaelis-Menten reader and the binder, through Pint).
_TEMPLATE_UNREAD_UNIT = re.compile(
    r"(?<![A-Za-z])(?:mM|µM|μM|uM|nM|pM|mmol/L)(?![A-Za-z])|(?i:\bk?cal(?:orie)?s?\b)"
)

EXTRACTORS = CHEMISTRY_EXTRACTORS


# Detection, turn prep and the direct reply each ask about the same line, so one turn
# extracts once. Callers get their own copy, so none can change what the next one reads.
_CACHE_SIZE = 128


def extract_chemistry_intent(text: str) -> ChemistryIntent | None:
    """Return the first complete supported calculation, otherwise ``None``."""
    intent = _extract_chemistry_intent(text)
    return None if intent is None else intent.model_copy(deep=True)


@lru_cache(maxsize=_CACHE_SIZE)
def _extract_chemistry_intent(text: str) -> ChemistryIntent | None:
    if not text.strip() or len(text) > _MAX_TEXT_LENGTH:
        return None
    readers = UNIT_AWARE_EXTRACTORS if _TEMPLATE_UNREAD_UNIT.search(text) else EXTRACTORS
    text = read_scientific_numbers(text)
    for extractor in readers:
        try:
            intent = extractor(text)
        except Exception:
            # A solver call during extract, such as balancing, must not escape into the turn.
            # CancelledError is a BaseException and still propagates.
            logger.exception(
                "chemistry extractor %s failed",
                getattr(extractor, "__name__", extractor),
            )
            return None
        if intent is not None:
            return written_numbers(text, intent)
    # No template knew the phrasing: read it into a law in its own words.
    bound = bind_chemistry_intent(text)
    return None if bound is None else written_numbers(text, bound)
