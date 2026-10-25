"""Reject profile facts that assign the user a name they never claimed.

A word problem ("Bebe has 2 pens… Cal") is not an introduction. The account
name is a separate field and is not inferred from other people in the chat.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.services.text_normalize import collapse_ws

_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'"})

# Phrases that state who the user is by name.
_IDENTITY_MARKERS = (
    "user's name is ",
    "users name is ",
    "user name is ",
    "user is named ",
)
# Phrases that give the name the user chose to be called. A bare "also goes by" is
# only a nickname on a fact that already names the user, so a pet's nickname is not
# treated as the user's name.
_NICKNAME_MARKERS = (
    "user goes by ",
    "user also goes by ",
)
_BEFORE_MARKERS = (
    " is the user's name",
    " is the users name",
    " is the user name",
)
_BARE_IDENTITY = ("the user is ", "user is ")

# How the user says who they are, and how they ask to be called.
_IDENTITY_PREFIXES = (
    "my name is ",
    "my name's ",
    "i'm ",
    "i am ",
)
_CHOSEN_PREFIXES = (
    "call me ",
    "i go by ",
    "i also go by ",
    "i prefer to be called ",
    "i'd like to be called ",
    "i want to be called ",
)
_CLAIM_PREFIXES = (*_IDENTITY_PREFIXES, *_CHOSEN_PREFIXES)

# A fact that is only the user's name: "User's name is Sam", "The user is named Sam."
_PURE_NAME_SENTENCE = re.compile(
    r"(?:the )?(?:user(?:'s|s)? name is|user is named) (?P<name>[^\W\d_][\w'-]*)\.?",
    re.IGNORECASE,
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


def _keep(name: str) -> bool:
    return len(name) >= 2 and name not in _NOT_A_NAME


def _token_at(haystack: str, cursor: int) -> tuple[str, int]:
    while cursor < len(haystack) and haystack[cursor] == " ":
        cursor += 1
    end = cursor
    while end < len(haystack) and (haystack[end].isalpha() or haystack[end] in "-'"):
        end += 1
    return haystack[cursor:end].strip("-'"), end


def _names_after(haystack: str, marker: str) -> list[str]:
    found: list[str] = []
    start = 0
    while True:
        index = haystack.find(marker, start)
        if index < 0:
            return found
        name, _end = _token_at(haystack, index + len(marker))
        if _keep(name):
            found.append(name)
        start = index + len(marker)


def _names_before(haystack: str, marker: str) -> list[str]:
    found: list[str] = []
    start = 0
    while True:
        index = haystack.find(marker, start)
        if index < 0:
            return found
        end = index
        while end > 0 and haystack[end - 1] == " ":
            end -= 1
        cursor = end
        while cursor > 0 and (haystack[cursor - 1].isalpha() or haystack[cursor - 1] in "-'"):
            cursor -= 1
        name = haystack[cursor:end].strip("-'")
        if _keep(name):
            found.append(name)
        start = index + len(marker)


def _bare_identity(folded: str) -> list[str]:
    """'The user is Bebe' is a name. 'The user is a teacher' is not."""
    found: list[str] = []
    for marker in _BARE_IDENTITY:
        start = 0
        while True:
            index = folded.find(marker, start)
            if index < 0:
                break
            if marker == "user is " and folded[max(0, index - 4) : index] == "the ":
                start = index + len(marker)
                continue
            name, end = _token_at(folded, index + len(marker))
            if name == "named":
                start = index + len(marker)
                continue
            rest = folded[end:].strip(" .,;:!")
            if _keep(name) and not rest:
                found.append(name)
            start = index + len(marker)
    return found


def _identity_names(folded: str) -> list[str]:
    names: list[str] = []
    for marker in _IDENTITY_MARKERS:
        names.extend(_names_after(folded, marker))
    for marker in _BEFORE_MARKERS:
        names.extend(_names_before(folded, marker))
    names.extend(_bare_identity(folded))
    return names


def _unique(names: list[str]) -> list[str]:
    return list(dict.fromkeys(names))


def stated_user_names(text: str) -> list[str]:
    """Names this sentence says the user has ("User's name is Sam"), not a nickname."""
    folded = _fold(text)
    return _unique(_identity_names(folded)) if "user" in folded else []


def assigned_user_names(text: str) -> list[str]:
    """Names this sentence assigns to the user. Empty when it does not."""
    folded = _fold(text)
    if "user" not in folded:
        return []
    names = _identity_names(folded)
    for marker in _NICKNAME_MARKERS:
        names.extend(_names_after(folded, marker))
    if names:
        names.extend(_names_after(folded, "also goes by "))
    return _unique(names)


def _claimed(speech: str, name: str, prefixes: tuple[str, ...] = _CLAIM_PREFIXES) -> bool:
    for prefix in prefixes:
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


def is_unclaimed_user_name(
    text: str,
    transcript: str,
    existing_texts: Iterable[str] = (),
) -> bool:
    """True when a fact gives the user a name their own words did not claim.

    A name already stored as the user's name still counts. A later nickname
    ('I also go by Ben') must not drop the earlier 'User's name is Bini'.
    """
    names = assigned_user_names(text)
    if not names:
        return False
    known: set[str] = set()
    for existing in existing_texts:
        known.update(assigned_user_names(existing))
    speech = _user_speech(transcript)
    return any(name not in known and not _claimed(speech, name) for name in names)


def as_chosen_name(text: str, transcript: str) -> str:
    """ "User's name is Sam" as "User goes by Sam" when the user only asked to be called it.

    "Call me Sam" is the name they chose to be called, not a claim about who they are:
    saved as a nickname it stays beside a different profile name (``profile_name``),
    where a stated name that disagrees with the profile is left out of the prompt.
    """
    match = _PURE_NAME_SENTENCE.fullmatch(collapse_ws(text.translate(_APOSTROPHES)))
    if match is None:
        return text
    name = match.group("name")
    folded = _fold(name)
    speech = _user_speech(transcript)
    if _claimed(speech, folded, _IDENTITY_PREFIXES):
        return text
    if not _claimed(speech, folded, _CHOSEN_PREFIXES):
        return text
    return f"User goes by {name}"
