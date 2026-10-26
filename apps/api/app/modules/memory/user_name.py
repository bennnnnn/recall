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
  they gave in their own words that differs from the account name ("My name is Bill" on
  an account named William), is saved as "User goes by Bill", so it is honoured.
"""

from __future__ import annotations

import re

from app.modules.memory.name_claim import user_claimed_name
from app.services.text_normalize import collapse_ws

_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'"})
_NAME = r"[^\W\d_][\w'-]*"
# The fact's opening clause states the user's own name.
_STATED = re.compile(
    rf"(?:(?:(?:the )?user(?:'s|s)? )?name is|(?:the )?user is named) (?P<name>{_NAME})"
    rf"|(?P<before>{_NAME}) is the user'?s? name\b",
    re.IGNORECASE,
)
_NICKNAME = re.compile(rf"(?:(?:the )?user )?(?:also )?goes by (?P<name>{_NAME})", re.IGNORECASE)
_NAME_PART = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*")
# Shared first letters that make "Bini" a short form of "Binalfew".
_SHORT_FORM_PREFIX = 3


def _clean(text: str) -> str:
    return collapse_ws((text or "").translate(_APOSTROPHES))


def stated_user_name(text: str) -> str | None:
    """The name a fact says the user has ("User's name is Sam"), not a nickname."""
    match = _STATED.match(_clean(text))
    if match is None:
        return None
    return match.group("name") or match.group("before")


def names_the_user(text: str) -> bool:
    """The fact gives the user's own name or the name they go by."""
    return stated_user_name(text) is not None or _NICKNAME.match(_clean(text)) is not None


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
    match = _STATED.match(cleaned)
    if match is None or match.group("before"):
        return text
    name = match.group("name")
    stated = user_claimed_name(transcript, name, way="identity")
    chosen = user_claimed_name(transcript, name, way="chosen")
    if not (stated or chosen):
        return text
    if stated and agrees_with_profile(name, profile_name):
        return text
    rest = cleaned[match.end() :].rstrip(" .")
    return f"User goes by {name}{rest}"
