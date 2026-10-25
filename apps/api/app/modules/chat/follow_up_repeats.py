"""A follow-up question the chat already holds, by its words.

Live (2026-10-24, one study chat): "Why use Kelvin not Celsius?" came back under four
replies after the user had asked "Why is temperature in Kelvin for Charles's law?", and
one set offered "What if it was $-2x + 5 = 0$?" beside "How does it change for
$-2x + 5 = 0$?". A candidate repeats an earlier line (a user question, a suggestion
already shown, one kept just before it) when it is the same question, holds the same
equation, or names the same topic: its topic words and the line's match but for one, two
words or more ("kelvin" and "celsius" are the question, "why use … not" is its frame). A
problem statement or a long line names many topics, so a what-if on one of them is new.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.services.text_normalize import collapse_ws

# A word of four letters or more, in any script.
_WORD = re.compile(r"[^\W\d_]{4,}")
_MATH_SPAN = re.compile(r"\$([^$\n]+)\$")
_RELATION = re.compile(r"=|<|>|\\[lg]eq?\b|\\neq\b")
# Words every question frame uses; the topic is what is left.
_FRAME = frozenset(
    {
        "about",
        "also",
        "because",
        "change",
        "changes",
        "could",
        "does",
        "explain",
        "happen",
        "happens",
        "have",
        "instead",
        "into",
        "make",
        "matter",
        "mean",
        "means",
        "more",
        "same",
        "should",
        "than",
        "that",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "used",
        "what",
        "when",
        "where",
        "which",
        "will",
        "with",
        "work",
        "works",
        "would",
        "your",
    }
)
_MIN_TOPIC_WORDS = 2


def _topic(text: str) -> frozenset[str]:
    return frozenset(w for w in _WORD.findall(text.casefold()) if w not in _FRAME)


def _equations(text: str) -> frozenset[str]:
    """The equations in ``text``: "$x$" alone is a name, not a question's subject."""
    spans = (re.sub(r"\s+", "", span) for span in _MATH_SPAN.findall(text))
    return frozenset(span for span in spans if _RELATION.search(span))


def _folded(text: str) -> str:
    return collapse_ws(text).casefold().rstrip("?").strip()


def repeats_earlier(candidate: str, earlier: Iterable[str]) -> bool:
    """Whether ``candidate`` asks what one of the ``earlier`` lines already asked."""
    folded, topic, equations = _folded(candidate), _topic(candidate), _equations(candidate)
    for line in earlier:
        if not line:
            continue
        if folded == _folded(line) or (equations and equations & _equations(line)):
            return True
        if _same_topic(topic, _topic(line)):
            return True
    return False


def _same_topic(first: frozenset[str], second: frozenset[str]) -> bool:
    """One set of topic words inside the other, at most one word apart."""
    small, large = sorted((first, second), key=len)
    return len(small) >= _MIN_TOPIC_WORDS and small <= large and len(large) - len(small) <= 1
