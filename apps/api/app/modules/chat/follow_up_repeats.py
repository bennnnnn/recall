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
question, and its numbers are part of what it asks, in order, each with its sign, root,
fraction and unit: "What if the perimeter was 60 cm?", "slope 2/3" after "slope 3/2",
minus 5 m/s (typed with the minus sign) after "5 m/s" and "2 g" after "2 kg" are new.

Live (2026-11-02): "What if the time was 4 s?" and "What if t was 4 s?" were two of three
chips. Two what-ifs that set the same values, each with its unit, make the same change: one
question, unless both name what changes the same way (in words, or by symbols) and the names
differ ("the initial speed" and "the final speed", $v_i$ and $v_f$, x and y).

Live (2026-11-07): "What if $v_0$ was 30 m/s?", "… 40 m/s?" and "… 50 m/s?" were the
three chips under a thrown ball, though the prompt asks for one what-if per quantity. Within
one set, a second what-if that changes the same symbol is the same suggestion again.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.modules.chat.follow_up_units import SYMBOLS, quantities
from app.services.text_normalize import collapse_ws, straighten_apostrophes

# A word of four letters or more, in any script.
_WORD = re.compile(r"[^\W\d_]{4,}")
_MATH_SPAN = re.compile(r"\$([^$\n]+)\$")
# A question read word by word: a maths span whole, a word or a number, a sign or a root.
_TOKEN = re.compile(r"\$[^$\n]+\$|[^\W_]+(?:\.\d+)?|[-+*/^=<>%\u221a]")
# What a reworded question drops or swaps without asking anything else: "the", "it", "my".
# Not "a": in "What if a = 2?" it is the variable.
_ARTICLES_AND_PRONOUNS = frozenset(
    "an the it its this that these those i you we he she they me him her us them my your "
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
_WHAT_IF = re.compile(r"^\s*(?:what|and)\s+(?:if|happens\s+if|would\s+happen\s+if)\b", re.I)
# A symbol written bare: "t", "x", "v_f", "v_{0}"; not the article "a" or the pronoun "I".
_BARE_SYMBOL = re.compile(r"(?<![\w$\\])(?![aAI]\b)[A-Za-z](?:_(?:\{[^{}]*\}|[A-Za-z0-9]+))?(?!\w)")


def _topic(text: str) -> frozenset[str]:
    """Its topic words, and the numbers it names outside maths as one item, in order, each
    with its unit read one way ("2 seconds" is "2 s"; equations match whole)."""
    words = [w for w in _WORD.findall(text.casefold()) if w not in _FRAME]
    numbers = [str(quantity) for quantity in quantities(_MATH_SPAN.sub(" ", text))]
    return frozenset([*words, "#" + "|".join(numbers)] if numbers else words)


def _equations(text: str) -> frozenset[str]:
    """The equations in ``text``: "$x$" alone is a name, not a question's subject."""
    spans = (re.sub(r"\s+", "", span) for span in _MATH_SPAN.findall(text))
    return frozenset(span for span in spans if _RELATION.search(span))


def _folded(text: str) -> str:
    """The question's words in order, without articles and pronouns, maths unspaced."""
    tokens = _TOKEN.findall(straighten_apostrophes(collapse_ws(text)).translate(SYMBOLS).casefold())
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
        if _same_change(candidate, line):
            return True
    return False


def _change(text: str) -> tuple[str, frozenset[str], frozenset[str]] | None:
    """A what-if's new values (each with its unit) and its names for what changes: its
    words, and its symbols. None for another question, or a value without a unit ("What if
    x was 4?" says which x by its letter alone)."""
    if not _WHAT_IF.match(text):
        return None
    plain = _MATH_SPAN.sub(" ", text)
    values = quantities(plain)
    if not values or any(value.unit is None for value in values):
        return None
    words = frozenset(w for w in _WORD.findall(plain.casefold()) if w not in _FRAME)
    spans = (re.sub(r"\s+", "", span) for span in _MATH_SPAN.findall(text))
    bare = _BARE_SYMBOL.findall(re.sub(r"\d+(?:\.\d+)?\s*\S*", " ", plain))
    symbols = frozenset([*spans, *bare])
    return "|".join(str(value) for value in values), words, symbols


def _same_change(first: str, second: str) -> bool:
    """Two what-ifs setting the same values, not named apart: "the time" and "t" are one
    name written two ways; "the initial speed" and "the final speed" are two."""
    one, other = _change(first), _change(second)
    if one is None or other is None or one[0] != other[0]:
        return False
    for mine, theirs in ((one[1], other[1]), (one[2], other[2])):
        if mine and theirs and mine != theirs:
            return False
    return True


def _same_topic(first: frozenset[str], second: frozenset[str]) -> bool:
    """One set of topic words inside the other, at most one word apart. Numbers alone are
    no topic: "What is 3 + 5?" and "Why does 3 + 5 make 8?" ask two things."""
    small, large = sorted((first, second), key=len)
    if len(small) < _MIN_TOPIC_WORDS or not any(_WORD.fullmatch(word) for word in small):
        return False
    return small <= large and len(large) - len(small) <= 1


# The symbol right after "what if", in maths or bare: $v_0$, $v_0 = 10$, v0, v_{0}. Not "a"
# or "I", which open words ("What if a ball…").
_SYMBOL_AFTER = re.compile(r"(?![aAI]\b)([A-Za-z](?:_\{?[A-Za-z0-9]{1,3}\}?|\d{1,2})?)(?=\s|=|$)")


# A value set inside an equation: a number, then nothing, a LaTeX unit or a spaced unit with no
# operator. "$v_0 = 30\\text{ m/s}$" sets v_0; "$y = 3x + 1$" and "$y = 3x$" set no value.
_SETS_A_VALUE = re.compile(
    r"^\s*([^=<>]+?)\s*=\s*-?\d[\d.,]*(?:\s*\\.*|\s+[^+\-=<>]*|\s*[%°].*)?\s*$"
)
# A question that sets a value as its condition: "How high with $v_0 = 30$?", "… if $g = 1.6$".
# "Why is $g = 9.8$ here?" explains the value it names, and "the speed at $t = 2$ s" and "the
# height at $t = 4$ s" ask two things about one variable: neither changes a quantity.
_CONDITION_SPAN = re.compile(r"\b(?:with|if)\s+(\$[^$\n]+\$)", re.IGNORECASE)


def changed_symbol(text: str) -> str | None:
    """The symbol a question changes to a new number, one way however it is written: "What
    if $v_0$ was 30 m/s?", "What if $v_0 = 10\\text{ m/s}$?", "What if v0 was 40 m/s?" and
    "How high with $v_0 = 30$ m/s?" all change v0. None for a what-if in words ("What if air
    resistance mattered?"), an equation ("What if $y = 3x + 1$?"), a what-if with no number
    ("What if n is even?") or a question that explains a value ("Why is $g = 9.8$ here?")."""
    opening = _WHAT_IF.match(text)
    if opening is None:
        condition = _CONDITION_SPAN.search(text)
        setting = _SETS_A_VALUE.match(condition.group(1)[1:-1]) if condition else None
        return _symbol_key(setting.group(1)) if setting is not None else None
    rest = text[opening.end() :].lstrip()
    if not re.search(r"\d", rest):
        return None
    span = _MATH_SPAN.match(rest)
    if span is not None:
        if not _RELATION.search(span.group(1)):
            return _symbol_key(span.group(1))
        setting = _SETS_A_VALUE.match(span.group(1))
        return _symbol_key(setting.group(1)) if setting is not None else None
    bare = _SYMBOL_AFTER.match(rest)
    return _symbol_key(bare.group(1)) if bare is not None else None


def _symbol_key(name: str) -> str | None:
    """v_{0}, v_0 and v0 as one key; None when ``name`` is no single symbol ("3x + 3")."""
    folded = re.sub(r"[\s{}_]", "", name)
    return folded if re.fullmatch(r"\\?[A-Za-z][A-Za-z0-9]{0,4}", folded) else None


def changes_a_kept_symbol(candidate: str, kept: Iterable[str]) -> bool:
    """Whether ``candidate`` is a what-if on a symbol one of ``kept`` already changes."""
    name = changed_symbol(candidate)
    return name is not None and any(changed_symbol(line) == name for line in kept)
