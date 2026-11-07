"""The thing a release question names: "is iPhone 19 out?" asks about the iPhone 19.

The search ranks its hits by it (``model_match``): a page about a much older model of the
thing goes. A product, a title or a model is what makes "out" a release: "is the power
out", "Is Tom out yet?" and "is the cake out" name none.

Match against ``collapse_ws``-normalized input (single spaces).
"""

from __future__ import annotations

import re

from app.modules.web_search.patterns import collapse_ws

# "Is iPhone 19 out (yet)?", "has GTA 6 been released", "did season 5 drop", "when does
# Windows 12 come out", "when will the new Zelda be released". The thing is a group.
_OUT = r"(?:released|launched|announced|out|dropped|available|on sale)"
_RELEASE_ASK = re.compile(
    r"^(?:(?:so|wait|hey|btw|ok|okay|and)\s*,?\s+)?(?:"
    rf"(?:is|are|was|were) (?P<is>.{{2,48}}?) (?:already |finally |even )?{_OUT}"
    r"|(?:has|have) (?P<has>.{2,48}?) (?:been (?:released|launched|announced)|come out"
    r"|came out|dropped|launched|released)"
    r"|did (?P<did>.{2,48}?) (?:come out|drop|launch|release|get released)"
    r"|when (?:is|are|will|does|do|did|was|were) (?P<when>.{2,48}?) (?:(?:be |get )?"
    r"(?:released|launched|announced|out|available)|com(?:e|ing) out|came out"
    r"|drop(?:ping)?|launch(?:ing)?|releas(?:e|ing)|going to (?:come out|be released|drop"
    r"|launch))"
    r")(?: (?:on|in) [\w+ ]{2,20}?)?(?: (?:yet|already|now|yet or not))?[\s?!.]*$",
    re.IGNORECASE,
)
# A release date the question prices or works out is no release: "if apples cost $2 each".
NOT_A_PRICE = re.compile(
    # A price the question states is a word problem: "if apples cost $2 each".
    r"[$€£¥] ?\d|[=+*/^]|\b(?:each|per)\b|"
    r"\bprice of (?:freedom|fame|success|love|happiness|war|peace|progress|beauty|greatness|"
    r"silence|admission)\b|\bprice (?:elasticity|discrimination|ceiling|floor|gouging|war|"
    r"index|level|point)s?\b|\bpricing (?:strategy|model|page|plan)\b"
    r"|\b(?:what|how) (?:should|would|do|can) (?:i|we) (?:price|charge)\b|\bprice (?:my|our)\b"
    r"|\b(?:write|draft|compose|rewrite|edit|proofread)\b",
    re.IGNORECASE,
)
# "GTA 6 release date", "release date of the iPhone 19".
_RELEASE_DATE = re.compile(r"\b(?:release|launch) date\b", re.IGNORECASE)
# Words a release names: "the new Kendrick album", "Stranger Things season 5".
_RELEASE_NOUN = re.compile(
    r"\b(?:games?|movies?|films?|albums?|songs?|singles?|seasons?|episodes?|series|sequel"
    r"|trailer|updates?|versions?|models?|phones?|consoles?|books?|novels?|shows?|patch"
    r"|dlc|expansion|chapters?|manga|anime|mixtape|ios|android|macos|windows|iphone|ipad"
    r"|macbook|pixel|galaxy|playstation|xbox|switch|airpods|gpt|gemini|claude|llama)\b",
    re.IGNORECASE,
)
_NEW = re.compile(r"\b(?:new|next|upcoming)\b", re.IGNORECASE)
# "what's the" before a release date's thing ("of" or "for" after it is ``_bare_thing``'s).
_LEADING_WHAT = re.compile(r"^(?:what(?:'s| is)\s+)?(?:the\s+)?")
# A person, the user's own things or the world outside: "is my order out", "is the
# power out", "is it out yet" (the last reply's subject is the follow-up rule's).
_NOT_A_RELEASE = frozenset(
    {
        "it", "he", "she", "they", "you", "i", "we", "my", "your", "his", "her", "their",
        "our", "its", "this", "that", "there", "someone", "anyone", "everyone",
    }
)  # fmt: skip


def _names_a_release(thing: str) -> bool:
    """A product, a title or a model: a number, a release word, a name of two capitalized
    words ("Grand Theft Auto") or a new one ("the new Zelda"). One name alone may be a
    person ("is Tom out")."""
    words = thing.split()
    if not words or words[0].casefold() in _NOT_A_RELEASE:
        return False
    if any(char.isdigit() for char in thing) or _RELEASE_NOUN.search(thing):
        return True
    names = sum(1 for word in words if word[:1].isupper())
    # "The new Zelda", "the next Batman": one name is a title once it is new.
    return names >= 2 or (names == 1 and _NEW.search(thing) is not None)


def _bare_thing(thing: str) -> str:
    r"""``thing`` without "what's the" before it or "of" / "for" after it.

    ``re.sub(r"^(?:what(?:'s| is)\s+)?(?:the\s+)?|\s+(?:of|for)\s*$", "", thing).strip()``
    as an anchored match and a suffix check: its ``\s+`` read a run of spaces again from each
    of them (CodeQL py/polynomial-redos).
    """
    thing = _LEADING_WHAT.sub("", thing, count=1).rstrip()
    for word in ("of", "for"):
        rest = thing.removesuffix(word)
        if rest != thing and rest[-1:].isspace():
            return rest.strip()
    return thing.strip()


def released_thing(text: str) -> str | None:
    """What a release question asks about ("iPhone 19" in "Is iPhone 19 out?"), else None."""
    cleaned = collapse_ws(text)
    match = _RELEASE_ASK.match(cleaned)
    if match is not None:
        thing = next(group for group in match.groups() if group)
        return thing if _names_a_release(thing) else None
    if _RELEASE_DATE.search(cleaned) is None or NOT_A_PRICE.search(cleaned) is not None:
        return None
    thing = _RELEASE_DATE.sub(" ", cleaned).strip(" ?!.")
    thing = _bare_thing(thing)
    thing = re.sub(r"^(?:of|for)\s+", "", thing)
    return thing if thing and _names_a_release(thing) else None
