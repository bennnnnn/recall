"""Whether a stated temperature change is a fall, by the words that govern its value."""

from __future__ import annotations

import re

# A change the words say is a fall: "decreases by 10 °C", "cools 2 kg of water by 15 °C",
# "lower the temperature of 2 kg of water by 30 °C", "a 10 °C drop". The fall word governs the
# value: a rise word between them ("is dropped from 20 m and its temperature rises by 3 °C")
# makes it a rise.
_FALL_WORDS = (
    r"(?:decreas(?:e|es|ed|ing)|drop(?:s|ped|ping)?|fall(?:s|ing)?|fell|cool(?:s|ed|ing)?"
    r"|lower(?:s|ed|ing)?|reduc(?:e|es|ed|ing))"
)
_FALL_VERB = rf"\b{_FALL_WORDS}\b"
_RISE_WORD = re.compile(
    r"\b(?:ris(?:e|es|ing)|rose|increas\w*|rais\w*|heat(?:s|ed|ing)?|warm\w*|gain\w*)\b",
    re.IGNORECASE,
)
_FALL_BEFORE = re.compile(
    rf"{_FALL_VERB}(?P<between>(?:\s+[^\s.;?!]+){{0,8}}?)\s+by\s+$", re.IGNORECASE
)
_FALL_AFTER = re.compile(
    rf"^\s*(?:°\s*C|degrees?(?:\s+C(?:elsius)?)?|K)?\s*(?:{_FALL_WORDS})", re.IGNORECASE
)


def falls_by(lower: str, start: int, end: int) -> bool:
    """The temperature change written at ``start:end`` is a fall, by the words that govern
    it: final - initial is negative, so the heat Q = mcΔT is too (owner, 2026-11-20)."""
    before = _FALL_BEFORE.search(lower[max(0, start - 80) : start])
    if before is not None and not _RISE_WORD.search(before.group("between")):
        return True
    return _FALL_AFTER.match(lower[end : end + 30]) is not None
