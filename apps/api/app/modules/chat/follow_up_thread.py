"""Which subject problem a line follows up on, while it stays on that problem's topic.

Live (2026-10-25, one chat with the free model): two lines after a rectangle problem and a
chart of it, "cool. i'm going to lisbon next month for 4 days, what should i not miss?" got
"What if perimeter was 48 cm?" under its travel tips. Any line ending in "?" continued the
last problem within three user lines. A line continues it only while it is on the problem's
topic: one that names a topic of its own, two topic words or more nearly all new to the
problem, the user's lines since and the replies, has left it, and the lines after it cannot
reach back past it. A short line ("why?", "what about a square?", "explain the units")
names too little to leave, a word that asks about the problem, shows it or measures it
("draw", "chart", "how long", "hours") names no topic, and a follow-up the chat showed and
the user tapped stays. A read of the user's own to-do list follows up on nothing
(``related_questions``).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from app.modules.chat.continuation_subject import (
    BIOLOGY_CUES,
    is_new_problem_request,
    is_pure_continuation,
)
from app.modules.chat.follow_up_words import STOP_WORDS, TOPIC_WORD
from app.modules.chat.prompt_constants.routing import is_lightweight_chat_turn
from app.services.problem_followup import message_role_content
from app.services.subject_solving import detect_subject
from app.services.text_normalize import collapse_ws, straighten_apostrophes

# A follow-up ("why?") belongs to a problem a few user lines back; further is stale.
_THREAD_USER_TURNS = 3
_FOLLOW_UP_LEADS = frozenset(
    {
        "why",
        "how",
        "what",
        "when",
        "where",
        "which",
        "can",
        "could",
        "is",
        "are",
        "does",
        "do",
        "explain",
        "show",
        "give",
        "try",
        "solve",
        "find",
        "and",
        "but",
        "so",
        "if",
    }
)
# A what-if varies the open problem, whatever it changes: "what if it took 2 days?".
_WHAT_IF = re.compile(r"^(?:what|and) if\b", re.IGNORECASE)
# "doesn't" is "does", not the word "doesn"; "what's" is "what".
_CONTRACTION = re.compile(r"n't\b|'(?:s|re|ll|ve|m|d)\b")
# Two topic words name a topic; one ("what about a square?") is a detail of the problem.
_MIN_OWN_WORDS = 2
# A line still on the problem may bring new words with it: "Why do we divide distance by
# time to get speed?" names the bike's speed and three words more. More than this many
# new words for each one it shares, and the shared one is happenstance.
_NEW_PER_SHARED = 3
# A word the user's own lines used ties a line to the problem; one only a reply used is
# half a tie, since a long reply uses many words ("keeps" in a reply about a falling ball
# is not what "my wifi keeps dropping" is about).
_REPLY_WORD_TIE = 0.5
# Words that ask about the problem or show it: "explain the units", "can you draw it as a
# chart?", "what if it took twice as long?".
_ASKS_ABOUT_IT = """again another answer calculate change check correct different double easier
easy explain explanation figure find give half happen hard harder help instead matter mean
method part problem question quick same simple simpler simply solve step take teach tell took
triple twice understand work wrong chart diagram draw equation example formula graph number
picture plot result show table value visual"""
# Words that measure it: "how long would it take?", "why is the area in square centimeters?".
_MEASURES_IT = """centimeter centimetre cubic degree fast feet foot gram high hour inch joule
kelvin kilogram kilometer kilometre liter litre long many meter metre mile minute mole newton
often percent pound second square unit volt watt"""
# The chat's fillers, which a trip to Lisbon and a reply about a falling ball both use.
_FILLERS = """actually anyway anything cool even every first going gonna good great last maybe
next nice okay please real really right someone something still sure thank think very want
well"""
# None of them names a topic of its own. Singular: a word is compared without its plural "s".
_NAMES_NO_TOPIC = frozenset(f"{_ASKS_ABOUT_IT} {_MEASURES_IT} {_FILLERS}".split())


def subject_for_related(text: str) -> str | None:
    """Math, physics, chemistry, or biology. Anything else is skipped."""
    cleaned = collapse_ws(text)
    if not cleaned:
        return None
    detected = detect_subject(cleaned)
    if detected is not None:
        return detected
    lowered = cleaned.casefold()
    if any(cue in lowered for cue in BIOLOGY_CUES):
        return "biology"
    return None


def _continues_thread(text: str) -> bool:
    """A question or a "one more" about the open problem, not small talk."""
    cleaned = collapse_ws(text)
    if not cleaned or is_lightweight_chat_turn(cleaned):
        return False
    if is_pure_continuation(cleaned) or is_new_problem_request(cleaned):
        return True
    words = cleaned.casefold().split()
    return cleaned.endswith("?") or (bool(words) and words[0].strip(",.") in _FOLLOW_UP_LEADS)


def thread_problem(
    question: str, prior: Sequence[Any] | None, shown: Sequence[str] = ()
) -> str | None:
    """The subject problem this line follows up on, or None.

    "Why do we divide distance by time?" names no subject itself, so the
    follow-ups would stop after the first tapped "why". It still belongs to
    the bike problem two lines back. A line about a trip to Lisbon does not,
    and neither does one after it. A follow-up the chat ``shown`` and the user
    tapped was written for the problem, whatever new words it brings.
    """
    if subject_for_related(question) is not None:
        return question
    if not prior or not _continues_thread(question):
        return None
    since: list[tuple[str, str]] = []
    users = 0
    for message in reversed(prior):
        role, content = message_role_content(message)
        if role not in ("user", "assistant") or not content or not content.strip():
            continue
        if role == "user":
            users += 1
            if users > _THREAD_USER_TURNS:
                return None
            if subject_for_related(content) is not None:
                lines = [*since[::-1], ("user", question)]
                return content if _stays_on_problem(content, lines, shown) else None
        since.append((role, content))
    return None


def _stays_on_problem(problem: str, since: list[tuple[str, str]], shown: Sequence[str]) -> bool:
    """Whether every user line in ``since`` (the chat after ``problem``, oldest first) is
    still on its topic: the words the chat used before it."""
    tapped = {_folded(line) for line in shown}
    asked, replied = _topic_words(problem), set[str]()
    for role, content in since:
        if role == "assistant":
            replied |= _topic_words(content)
            continue
        if _folded(content) not in tapped and _names_a_new_topic(content, asked, replied):
            return False
        asked |= _topic_words(content)
    return True


def _names_a_new_topic(line: str, asked: set[str], replied: set[str]) -> bool:
    """Two topic words or more, nearly all new to what the user asked and the replies."""
    cleaned = collapse_ws(line)
    if _WHAT_IF.match(cleaned):
        return False
    own = _topic_words(cleaned)
    new = own - asked - replied
    ties = len(own & asked) + _REPLY_WORD_TIE * len((own & replied) - asked)
    return len(new) >= _MIN_OWN_WORDS and len(new) > _NEW_PER_SHARED * ties


def _folded(text: str) -> str:
    return collapse_ws(text).casefold()


def _topic_words(text: str) -> set[str]:
    """The words that say what ``text`` is about, each without its plural "s"."""
    folded = _CONTRACTION.sub("", straighten_apostrophes(collapse_ws(text)).casefold())
    words = (_singular(word) for word in TOPIC_WORD.findall(folded) if word not in STOP_WORDS)
    return {word for word in words if word not in _NAMES_NO_TOPIC}


def _singular(word: str) -> str:
    return word[:-1] if word.endswith("s") and not word.endswith("ss") else word
