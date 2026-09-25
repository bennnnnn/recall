"""Reject profile facts that assign the user a name they never claimed.

A word problem ("Bebe has 2 pens… Cal") is not an introduction. The account
name is a separate field and is not inferred from other people in the chat.
"""

from __future__ import annotations

_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'"})

# Markers that assign a name to the user. "goes by" alone is too broad.
_NAME_MARKERS = (
    "user's name is ",
    "users name is ",
    "user name is ",
    "user is named ",
    "user goes by ",
    "also goes by ",
)

_CLAIM_PREFIXES = (
    "my name is ",
    "my name's ",
    "i'm ",
    "i am ",
    "call me ",
    "i go by ",
    "i also go by ",
)

_NOT_A_NAME = frozenset({"the", "a", "an", "my", "not", "unknown", "missing", "none", "user"})


def _fold(text: str) -> str:
    return (text or "").translate(_APOSTROPHES).casefold()


def _user_speech(transcript: str) -> str:
    """User lines only. A transcript with no role labels is treated as the user."""
    raw = transcript or ""
    lines = raw.splitlines() or [raw]
    has_role = False
    for line in lines:
        lowered = line.strip().casefold()
        if lowered.startswith("user:") or lowered.startswith("assistant:"):
            has_role = True
            break
    if not has_role:
        return _fold(raw)
    parts: list[str] = []
    in_user = False
    for raw_line in lines:
        line = raw_line.strip()
        lowered = line.casefold()
        if lowered.startswith("assistant:"):
            in_user = False
            continue
        if lowered.startswith("user:"):
            in_user = True
            line = line.split(":", 1)[1].strip()
            if line:
                parts.append(line)
            continue
        if in_user and line:
            parts.append(line)
    return _fold("\n".join(parts))


def _names_after(haystack: str, marker: str) -> list[str]:
    found: list[str] = []
    start = 0
    while True:
        index = haystack.find(marker, start)
        if index < 0:
            return found
        cursor = index + len(marker)
        while cursor < len(haystack) and haystack[cursor] == " ":
            cursor += 1
        end = cursor
        while end < len(haystack) and (haystack[end].isalpha() or haystack[end] in "-'"):
            end += 1
        name = haystack[cursor:end].strip("-'")
        if len(name) >= 2 and name not in _NOT_A_NAME:
            found.append(name)
        start = index + len(marker)


def _claimed(speech: str, name: str) -> bool:
    for prefix in _CLAIM_PREFIXES:
        phrase = prefix + name
        start = 0
        while True:
            index = speech.find(phrase, start)
            if index < 0:
                break
            before_ok = index == 0 or not speech[index - 1].isalnum()
            after = index + len(phrase)
            possessive = after < len(speech) and speech[after] == "'"
            after_ok = after >= len(speech) or not speech[after].isalnum()
            if before_ok and after_ok and not possessive:
                return True
            start = index + 1
    return False


def is_unclaimed_user_name(text: str, transcript: str) -> bool:
    """True when a fact gives the user a name their own words did not claim."""
    folded = _fold(text)
    if "user" not in folded:
        return False
    names: list[str] = []
    for marker in _NAME_MARKERS:
        names.extend(_names_after(folded, marker))
    if not names:
        return False
    speech = _user_speech(transcript)
    return any(not _claimed(speech, name) for name in names)
