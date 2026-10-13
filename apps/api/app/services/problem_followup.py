"""The parts of a short subject follow-up that do not depend on the subject.

Physics and chemistry each replay their previous problem when a line only
continues it: explain the result, ask for another quantity of the same setup,
or replace one named given. Each subject keeps its own asks, units and check
that the rewrite verifies; the message reading, the adjacent exchange, the
"explain it" phrases and the text rewrites are the same for both and live here.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from app.services.law_binding.givens import Given

# A line that asks only to have the previous result explained, read lowercase.
EXPLAIN_RE = re.compile(
    r"^(?:"
    r"why(?: is (?:it|that)(?: [-+]?\d+(?:\.\d+)?(?: [a-zμµ°/^0-9.]+)?)?)?"
    r"|how(?: come| did you get (?:that|it)| does that work)?"
    r"|i (?:didn't|did not|don't|do not) (?:get|understand)(?: it)?"
    r"|help me understand(?: it)?"
    r"|(?:that(?:'s| is)|this is|i(?:'m| am)) confus(?:ed|ing)"
    r")$"
)

_ASK_SENTENCE = re.compile(r"\b(?:find|what|calculate|determine|how)\b", re.IGNORECASE)
_NAME_FILLER = re.compile(r"\b(?:final|initial|the|its|a|an)\b")


def message_role_content(message: Any) -> tuple[str | None, str | None]:
    """(role, content) of a chat message: a pair, a mapping, or a row with attributes."""
    if isinstance(message, tuple) and len(message) == 2:
        role, content = message
        if isinstance(role, str) and isinstance(content, str):
            return role, content
        return None, None
    if isinstance(message, Mapping):
        role = message.get("role")
        content = message.get("content")
    else:
        role = getattr(message, "role", None)
        content = getattr(message, "content", None)
    if not isinstance(role, str) or not isinstance(content, str):
        return None, None
    return role, content


def adjacent_problem(recent: Sequence[Any], is_subject: Callable[[str], bool]) -> str | None:
    """The user's problem in the last exchange, when it was answered and is this subject's."""
    if len(recent) < 2:
        return None
    role, prior = message_role_content(recent[-2])
    answer_role, answer = message_role_content(recent[-1])
    if role != "user" or answer_role != "assistant":
        return None
    if not prior or not prior.strip() or not answer or not answer.strip():
        return None
    if not is_subject(prior):
        return None
    return prior


def followup_line(query: str | None) -> str | None:
    """The line with its quotes, outer punctuation and repeated spaces taken off."""
    if not query or not query.strip():
        return None
    text = " ".join(query.replace("\u2019", "'").split()).strip(" \"'`")
    text = text.strip(".,!?:;")
    return text or None


def ask_replaced(prior: str, phrase: str) -> str:
    """The prior problem asking "Find the <phrase>." in place of its own ask sentence."""
    parts = re.split(r"(?<=[.?!])\s+", prior.strip())
    replacement = f"Find the {phrase}."
    if parts and _ASK_SENTENCE.search(parts[-1]):
        parts[-1] = replacement
        return " ".join(parts)
    return prior.rstrip(".?! ") + ". " + replacement


def given_name(name: str) -> str:
    """The quantity a changed given names, without "the", "its", "final" and the like."""
    return " ".join(_NAME_FILLER.sub(" ", name).split())


def replace_given(text: str, given: Given, value: str, unit: str) -> str:
    """The text with one given, and the unit written after it, replaced."""
    end = given.end
    tail = text[end:]
    old_unit = re.match(r"[ \t]*" + re.escape(given.unit), tail, re.IGNORECASE)
    if old_unit is not None:
        end += old_unit.end()
    return text[: given.start] + f"{value} {unit}" + text[end:]
