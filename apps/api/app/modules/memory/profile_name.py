"""The profile name is the user's name: a saved fact that names them otherwise stays out.

The account name (``users.name``, Settings → Profile) is what the prompt calls the user.
On an account named Dev, saved memory held "User's name is Sam; they are a nursing
student living in Chicago": replies switched between the two names, apologised for
the switch, and once told the user that "the memory block" named a different person
(live chats, 2026-10-25). A fact line that states a different name is left out of the
memory block every prompt reads, so the prompt holds one name.

What stays: a name the user chose to be called ("User goes by Sam", what "call me Sam"
saves as, ``name_claim.as_chosen_name``; "User's name is Dev; also goes by Sam"), a
short form of the profile name ("Bini" on an account named Binalfew), and every name
fact when no profile name is set. The block is filtered as text, after its cache, so a
renamed profile takes effect on the next turn.
"""

from __future__ import annotations

import re

from app.modules.memory.facts import SECTION_LABELS
from app.modules.memory.name_claim import stated_user_names

_PROFILE_HEADING = f"## {SECTION_LABELS['profile']}"
# The notes ``facts._fact_line`` adds after a fact: "(said 2026-10)", "(unconfirmed)".
_LINE_NOTES = re.compile(r" \((?:said \d{4}-\d{2})?(?:, )?(?:unconfirmed)?\)$")
_NAME_PART = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*")
# Shared first letters that make "Bini" a short form of "Binalfew".
_SHORT_FORM_PREFIX = 3


def _name_parts(name: str | None) -> list[str]:
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


def names_another_person(fact: str, profile_name: str | None) -> bool:
    """True when ``fact`` states a name for the user that the profile name does not have."""
    parts = _name_parts(profile_name)
    if not parts:
        return False
    stated = [_name_parts(name)[0] for name in stated_user_names(fact) if _name_parts(name)]
    if not stated:
        return False
    return not any(_agrees(name, part) for name in stated for part in parts)


def without_conflicting_names(block: str, profile_name: str | None) -> str:
    """The memory block without a Profile line that names the user differently."""
    if not block or _PROFILE_HEADING not in block or not _name_parts(profile_name):
        return block
    lines = block.split("\n")
    kept: list[str] = []
    in_profile = False
    for line in lines:
        if line.startswith("## "):
            in_profile = line.strip() == _PROFILE_HEADING
        elif in_profile and line.startswith("- "):
            fact = _LINE_NOTES.sub("", line[2:].strip())
            if names_another_person(fact, profile_name):
                continue
        kept.append(line)
    return block if len(kept) == len(lines) else _without_empty_sections(kept)


def _without_empty_sections(lines: list[str]) -> str:
    """Drop a heading left with no facts under it, and the block when none are left."""
    out: list[str] = []
    for index, line in enumerate(lines):
        if line.startswith("## ") and not _has_fact_after(lines, index):
            if out and not out[-1].strip():
                out.pop()
            continue
        out.append(line)
    if not any(line.startswith("- ") for line in out):
        return ""
    return "\n".join(out)


def _has_fact_after(lines: list[str], heading: int) -> bool:
    for line in lines[heading + 1 :]:
        if line.startswith("## "):
            return False
        if line.startswith("- "):
            return True
    return False
