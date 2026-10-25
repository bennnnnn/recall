"""A follow-up question the chat already holds, by its words.

Live (2026-10-24, one study chat): "Why use Kelvin not Celsius?" came back under four
replies after the user had asked "Why is temperature in Kelvin for Charles's law?", and
one set offered "What if it was $-2x + 5 = 0$?" beside "How does it change for
$-2x + 5 = 0$?". A candidate repeats an earlier line (a user question, a suggestion
already shown, one kept just before it) when it is the same question, holds the same
equation, or names the same topic: its topic words and the line's match but for one, two
words or more ("kelvin" and "celsius" are the question, "why use … not" is its frame). A
problem statement or a long line names many topics, so a what-if on one of them is new.

Live again (2026-10-25): "What if perimeter was 48 cm?" came back after "What if the
perimeter was 48 cm?". The same question without its articles and pronouns is the same
question, and a number is part of what it asks: "perimeter" and 48 are its topic, so
"What if the perimeter was 60 cm?" is new.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.services.text_normalize import collapse_ws, straighten_apostrophes

# A word of four letters or more, in any script.
_WORD = re.compile(r"[^\W\d_]{4,}")
# A number standing alone, with its sign: 48 in "48 cm" and -5 in "-5 m/s", not the 2 of "2w".
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?!\w|\.\d)")
_MATH_SPAN = re.compile(r"\$([^$\n]+)\$")
# A question read word by word: a maths span whole, a word or a number, a sign.
_TOKEN = re.compile(r"\$[^$\n]+\$|[^\W_]+(?:\.\d+)?|[-+*/^=<>%]")
# What a reworded question drops or swaps without asking anything else: "the", "it", "my".
_ARTICLES_AND_PRONOUNS = frozenset(
    "a an the it its this that these those i you we he she they me him her us them my your "
    "our his their".split()
)
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
    """Its topic words, and the numbers it names outside maths (equations match whole)."""
    folded = text.casefold()
    words = (w for w in _WORD.findall(folded) if w not in _FRAME)
    return frozenset((*words, *_NUMBER.findall(_MATH_SPAN.sub(" ", folded))))


def _equations(text: str) -> frozenset[str]:
    """The equations in ``text``: "$x$" alone is a name, not a question's subject."""
    spans = (re.sub(r"\s+", "", span) for span in _MATH_SPAN.findall(text))
    return frozenset(span for span in spans if _RELATION.search(span))


def _folded(text: str) -> str:
    """The question's words in order, without articles and pronouns, maths unspaced."""
    tokens = _TOKEN.findall(straighten_apostrophes(collapse_ws(text)).casefold())
    kept = (re.sub(r"\s+", "", t) for t in tokens if t not in _ARTICLES_AND_PRONOUNS)
    return " ".join(kept)


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
    """One set of topic words inside the other, at most one word apart. Numbers alone are
    no topic: "Why does 3 + 4 equal 7?" and "How can 4 + 3 also make 7?" ask two things."""
    small, large = sorted((first, second), key=len)
    if len(small) < _MIN_TOPIC_WORDS or not any(_WORD.fullmatch(word) for word in small):
        return False
    return small <= large and len(large) - len(small) <= 1
