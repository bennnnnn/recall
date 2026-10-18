"""Is this turn about a fact out in the world? Then the search classifier decides.

The classifier used to run only on a "live" word (current, latest, price, who
is…). Everything else kept the regex answer, which is almost always no, and the
model answered from memory: "what's the population of Ethiopia", "who won the
Champions League", "best restaurants in Addis", "is Abiy Ahmed responsible for
the Tigray war" never reached the classifier. This decides only whether to ask
it; the classifier reads the turn and the chat and says whether to search.

Cheap shapes rule the classifier out where it can only say no: maths and code,
how-to, a one-concept definition ("what is photosynthesis"), and requests to
write, explain, teach, translate or plan.
"""

from __future__ import annotations

import re

from app.modules.web_search.patterns import collapse_ws, looks_like_math_or_code

# Asks about something: a question word, a yes/no opener, or a "best X" list.
_ASKS = re.compile(
    r"^(?:(?:and|so|but|ok(?:ay)?|hey|also)[ ,]+)?"
    r"(?:who(?:'s|se|m)?|what(?:'s)?|which|when|"
    r"how\s+(?:many|much|old|long|big|tall|far|often|rich|large|high)|"
    r"is|are|was|were|did|does|has|have|will|"
    r"tell\s+me\s+about|list|name|"
    r"(?:the\s+)?(?:best|top|cheapest|biggest|largest|richest|most\s+popular)\b)\b",
    re.IGNORECASE,
)
# "Can you tell me…" is a polite way in to the same question.
_POLITE = re.compile(
    r"^(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?(?:tell\s+me\s+)?|please\s+)",
    re.IGNORECASE,
)
# A claim about someone named mid-sentence ("But Ahmed caused the war"). A
# capital after a sentence break is only a new sentence; "I" is the user.
_NAMED = re.compile(r"(?<![.!?]\s)(?<!^)\b(?!I\b)[A-Z][a-z]+")
_MIN_CLAIM_WORDS = 4

# Nothing in these is a fact to look up.
_NOT_A_LOOKUP = re.compile(
    r"^(?:(?:can|could|would|will)\s+you\s+|please\s+)?"
    r"(?:how\s+(?:do|can|should|would|could|to)\b|why\b|"
    r"write|draft|compose|rewrite|edit|proofread|translate|summari[sz]e|explain|define|"
    r"teach|help\s+me|make|create|generate|draw|plan|give\s+me\s+\d+\s+\w+|"
    r"what\s+does\s+\S+\s+mean|"
    # An explanation, not a record: "what causes weather", "the benefits of water".
    r"what\s+(?:causes|makes|happens|is\s+the\s+difference|are\s+the\s+"
    r"(?:benefits|pros|cons|signs|symptoms|types|uses))\b|"
    # The clock answers these: "what time is it in Tokyo", "what day is it".
    r"what\s+time\s+is\s+it|what(?:'s|\s+is)\s+the\s+(?:time|date)\b|what\s+day\s+is\b|"
    # Counting units: "how many minutes in a good nap".
    r"how\s+(?:many|much)\s+(?:seconds|minutes|hours|days|weeks|months|years|calories|"
    r"grams|cups|ounces|spoons|teaspoons|tablespoons|litres|liters|steps|reps)\b)",
    re.IGNORECASE,
)
# About the assistant or the user: "what can you do", "what is my dog's name".
_ABOUT_US = re.compile(
    r"\b(?:you|your|yours|yourself|my|mine|our|ours)\b|^i(?:'m|'ve|'d|'ll)?\b|^im\b",
    re.IGNORECASE,
)
# "What is photosynthesis", "what's a prime minister": one concept, its meaning.
_DEFINITION = re.compile(
    r"^what(?:'s|\s+is|\s+are)\s+(?:an?\s+|the\s+)?[\w-]+(?:\s+[\w-]+)?\s*\??$",
    re.IGNORECASE,
)


def asks_about_the_world(text: str) -> bool:
    """True when a turn may hinge on a real-world fact the model could have wrong."""
    cleaned = _POLITE.sub("", collapse_ws(text))
    if not cleaned or looks_like_math_or_code(cleaned) or _ABOUT_US.search(cleaned):
        return False
    if _NOT_A_LOOKUP.match(cleaned) or _DEFINITION.match(cleaned):
        return False
    if _ASKS.match(cleaned):
        return True
    return len(cleaned.split()) >= _MIN_CLAIM_WORDS and _NAMED.search(cleaned) is not None
