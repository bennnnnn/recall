"""A checklist the user asked for: Markdown task lines the phone draws as checkboxes.

"Give me a packing checklist" came back as bold-led bullets, with nothing to
tick. The phone renders ``- [ ]`` / ``- [x]`` (GFM task lists) as boxes, so an
explicit request for a checklist, to-do list or task list asks for them. A
list that is only mentioned ("thanks for the checklist"), one that already
exists ("send me my to-do list"), or how to make one in an app ("a checklist in
Notion") is not a request for one.
"""

from __future__ import annotations

import re

from app.modules.chat.prompt_constants.coding import is_programming_turn

CHECKLIST_FORMAT_HINT = (
    "This turn asked for a checklist. Write every item to tick off as a Markdown task "
    "line, `- [ ] Item`, so it shows as a checkbox; nothing else in the list. Group items "
    "under short `###` headings when they fall into categories. One line per item: the "
    "thing, then a few words of detail after a colon only when it helps. Use `- [x]` only "
    "for an item the user said is already done. Never a pipe table."
)

_CHECKLIST = r"check-?lists?"
_LIST = rf"(?:{_CHECKLIST}|to-?do\s+lists?|task\s+lists?)"
# Between the verb and the list: words of the list's name only. A preposition
# ("thoughts on my checklist"), "sure" ("make sure the checklist covers…") or
# a list the user already has ("send me my to-do list") is not a new list.
_NAME_GAP = r"(?:(?!\b(?:to|on|about|with|in|from|at|of|for|by|sure|my|our)\b)[^.?!\n]){0,60}?"
# Words that open a remark about a checklist ("thanks for the checklist").
_NOT_A_NAME = (
    r"(?:thanks?|thank\s+you|love|loved|like|liked|great|nice|cool|awesome|perfect|ok|okay|"
    r"my|your|our|the|this|that|where|why|how|who|when|is|are|did|do|does|can|could|"
    r"should|would|will)\b"
)

_CHECKLIST_REQUEST = re.compile(
    r"(?:"
    # "make me a checklist", "I need a moving checklist", "write a task list".
    rf"\b(?:give|make|create|write|draft|prepare|build|put\s+together|send|need|want|"
    rf"generate|turn)\b{_NAME_GAP}\b{_LIST}\b|"
    # "checklist for a trip", "as a checklist", "as a to-do list", "in checklist form".
    rf"\b{_CHECKLIST}\s+(?:for|of|before|when)\b|"
    rf"\b(?:as|into|in)\s+(?:a\s+)?{_CHECKLIST}\b|"
    rf"\b(?:as|into)\s+(?:a\s+)?{_LIST}\b|"
    rf"\b{_LIST}\s+form(?:at)?\b|"
    # The whole message is the checklist's name: "packing checklist".
    rf"^(?!{_NOT_A_NAME})(?:[^\W\d_][\w'\u2019-]*\s+){{1,4}}{_CHECKLIST}\W*$"
    r")",
    re.IGNORECASE,
)

# "What is a checklist?", "meaning of checklist": about the word, not a request.
_DEFINITION = re.compile(
    r"^\s*(?:what(?:'s|\u2019s|\s+is|\s+are)|define|meaning\s+of)\b", re.IGNORECASE
)
# A list in software: "a checklist component in React", "my task list app",
# "a checklist in Notion", "how do I make a to-do list in Excel".
_SOFTWARE = re.compile(
    rf"\b{_LIST}\s+(?:apps?|components?|widgets?|screens?|pages?|ui|features?|templates?|"
    r"functions?|class(?:es)?|tables?|schemas?|models?|apis?)\b|"
    rf"\b{_LIST}\s+(?:in|on|with|using)\s+(?:notion|excel|google\s+(?:docs|sheets|keep)|"
    r"sheets|word|trello|obsidian|onenote|evernote|todoist|jira|asana|clickup|airtable|"
    r"confluence|apple\s+notes|(?:the\s+)?[\w-]+\s+app)\b",
    re.IGNORECASE,
)

_MAX_SCAN = 400


def is_checklist_request(text: str) -> bool:
    """True when the user asked for a checklist, to-do list or task list to tick off."""
    cleaned = text.strip()[:_MAX_SCAN]
    if not cleaned or _DEFINITION.search(cleaned) or _SOFTWARE.search(cleaned):
        return False
    if is_programming_turn(cleaned):
        return False
    return bool(_CHECKLIST_REQUEST.search(cleaned))
