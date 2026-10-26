"""The user's name in saved memory, read against the name on their account.

The account name (``users.name``, Settings → Profile) is what the prompt calls the
user. A saved fact names the user only when it opens with an explicit marker for the
user's own name: "User's name is Sam", "The user is named Sam", "Sam is the user's
name", or a fact with no subject ("Name is Sam"). "User is retired", "User's sister's
name is Sam" and "User's Instagram user name is samx" name no one, so nothing here
touches them.

Two rules keep one name in the prompt (live chats, 2026-10-25: an account named Dev
with "User's name is Sam; they are a nursing student" in memory got both names):

- Read (``names_another_person``): a fact that states a name the account name does not
  have is left out. A short form agrees ("Bini" for "Binalfew"), and a nickname
  ("User goes by Sam") is not a stated name.
- Write (``as_chosen_name``): a name the user asked to be called ("call me Sam"), or one
  they said is their name and the account does not have ("My name is Bill" on an
  account named William), is saved as "User goes by Bill", so it is honoured. "I'm Sam"
  is not enough: "Pretend I'm Sam, a nursing student" is how the live fact arrived.

A name runs to the end of its clause and does not start in lower case, so "User's name
is pronounced BEE-nee" and "User goes by bike" name no one.
"""

from __future__ import annotations

import re

from app.modules.memory.name_claim import user_claimed_name
from app.services.text_normalize import collapse_ws

_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'"})
# A name runs to the end of its clause: "User's name is Sam; they nurse", "Sam and …".
_CLAUSE = r"[^;,.()]+?"
_CLAUSE_END = r"(?=\s*$|\s*[;,.()]|\s+(?:and|but|who|whose)\b)"
# The fact's opening clause states the user's own name.
_STATED = re.compile(
    rf"(?:(?:(?:the )?user(?:'s|s)? )?name is|(?:the )?user is named)"
    rf" (?P<name>{_CLAUSE}){_CLAUSE_END}"
    rf"|(?P<before>{_CLAUSE}) is the user'?s? name\b",
    re.IGNORECASE,
)
_NICKNAME = re.compile(
    rf"(?:(?:the )?user )?(?:also )?goes by (?P<name>{_CLAUSE}){_CLAUSE_END}", re.IGNORECASE
)
_NAME_WORD = re.compile(r"[^\W\d_][\w'-]*")
_NAME_PART = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*")
# Most words a clause can start with are lower case ("pronounced BEE-nee", "short for
# Bini", "bike to work"); these are the capitalised ones that still name no one.
_NOT_A_NAME = frozenset(
    {"the", "a", "an", "not", "unknown", "none", "he", "she", "they", "him", "her", "them"}
)
# A name is one to four words, each a word that does not start in lower case.
_MAX_NAME_WORDS = 4
# Shared first letters that make "Bini" a short form of "Binalfew".
_SHORT_FORM_PREFIX = 3


def _clean(text: str) -> str:
    return collapse_ws((text or "").translate(_APOSTROPHES))


def _as_name(candidate: str | None) -> str | None:
    """``candidate`` when it reads as a name ("Sam", "Sam Okafor"), else None."""
    words = (candidate or "").split()
    if not 0 < len(words) <= _MAX_NAME_WORDS or words[0].casefold() in _NOT_A_NAME:
        return None
    if any(not _NAME_WORD.fullmatch(word) or word[0].islower() for word in words):
        return None
    return " ".join(words)


def _stated(cleaned: str) -> tuple[str, re.Match[str]] | None:
    match = _STATED.match(cleaned)
    if match is None:
        return None
    name = _as_name(match.group("name") or match.group("before"))
    return (name, match) if name else None


def stated_user_name(text: str) -> str | None:
    """The name a fact says the user has ("User's name is Sam"), not a nickname."""
    found = _stated(_clean(text))
    return found[0] if found else None


def names_the_user(text: str) -> bool:
    """The fact gives the user's own name or the name they go by."""
    if stated_user_name(text) is not None:
        return True
    match = _NICKNAME.match(_clean(text))
    return match is not None and _as_name(match.group("name")) is not None


def _name_parts(name: object) -> list[str]:
    if not isinstance(name, str):
        return []
    return [part.casefold() for part in _NAME_PART.findall(name)]


def _agrees(stated: str, part: str) -> bool:
    """One name matches one part of the profile name, or is a short form of it."""
    if stated == part:
        return True
    shorter, longer = sorted((stated, part), key=len)
    if len(shorter) >= 2 and longer.startswith(shorter):
        return True
    prefix = _SHORT_FORM_PREFIX
    return len(shorter) >= prefix and shorter[:prefix] == longer[:prefix]


def agrees_with_profile(name: str, profile_name: str | None) -> bool:
    """True when ``name`` is the profile name, a part of it or a short form; or no profile name."""
    parts = _name_parts(profile_name)
    stated = _name_parts(name)
    if not parts or not stated:
        return True
    return any(_agrees(stated[0], part) for part in parts)


def names_another_person(fact: str, profile_name: str | None) -> bool:
    """True when ``fact`` states a name for the user that the profile name does not have."""
    stated = stated_user_name(fact)
    return stated is not None and not agrees_with_profile(stated, profile_name)


def as_chosen_name(text: str, transcript: str, profile_name: str | None = None) -> str:
    """ "User's name is Sam" saved as "User goes by Sam" when that is how to call them.

    It is when the user only asked to be called it ("call me Sam"), or when they said
    it is their name and the account has another ("My name is Bill" on William). The
    rest of the fact stays: "User goes by Bill; they teach maths". A name the user
    did not give in their own words is left for the claim gate (``name_claim``).
    """
    cleaned = _clean(text)
    found = _stated(cleaned)
    if found is None or found[1].group("before"):
        return text
    name, match = found
    first = name.split()[0]
    if user_claimed_name(transcript, first, way="identity") and agrees_with_profile(
        name, profile_name
    ):
        return text
    # "I'm Sam" against an account named Dev stays a stated name, which the read leaves
    # out: it is as often a role ("Pretend I'm Sam") as a name.
    if not (
        user_claimed_name(transcript, first, way="chosen")
        or user_claimed_name(transcript, first, way="named")
    ):
        return text
    rest = cleaned[match.end() :].rstrip(" .")
    return f"User goes by {name}{rest}"
