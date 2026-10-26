"""What a request clause is about, and whether it leans on the one before.

Chat's planner (``modules/chat/turn_prep/clauses``) cuts a message into requests with
these; the picture reader (``modules/images/gen_intent_second``) asks the same questions
so that "draw me a cat and tell me about cat breeds" stays one picture exactly when the
planner keeps it one request.
"""

from __future__ import annotations

import re

# A fresh task. "Include", "keep", "use", "avoid" only shape the request before them.
TASK_VERBS = (
    "tell explain describe define write draft compose give show find search look google "
    "recommend suggest list compare translate summarize summarise teach draw create generate "
    "design plan solve calculate compute convert graph plot remind switch change set turn "
    "build implement debug review proofread rewrite brainstorm quiz check add make help"
).split()

# "What time is it", "is it going to rain": an "it" that names nothing earlier.
_EMPTY_IT = re.compile(
    r"\b(?:what (?:time|day|date|year|month) is it|(?:time|day|date) it is|"
    r"(?:is|will) it (?:going to )?(?:be )?(?:rain|snow|cold|hot|warm|sunny|windy|cloudy)\w*|"
    r"it(?:'s| is) (?:going to )?(?:rain|snow)\w*|how (?:long|far) (?:does|will|would|is) it)\b",
    re.IGNORECASE,
)

_POINTS_BACK = re.compile(
    r"\b(?:it|its|itself|they|them|their|theirs|these|those|he|him|his|she|her|hers|each|"
    r"both|either|neither|the same|the former|the latter|the other|why not|"
    r"(?:what|how) about|same for|compared? (?:with|to|against)|"
    r"which (?:is|are|was|were|one|ones|to|should|would|will|of)|"
    r"one of (?:them|those|these)|(?:which|that|this|a good|the best|get|buy|pick|choose|"
    r"recommend) one)\b"
    # "Go there", not "is there a museum".
    r"|(?<!\bis )(?<!\bare )(?<!\bwas )(?<!\bwere )\bthere\b(?! (?:is|are|was|were)\b)(?!')"
    # "Is that true", not "how do I know that my code works" or "this week".
    r"|\b(?:that|this)\b(?! (?:my|your|our|the|a|an|i|you|we|week|weekend|year|month|"
    r"morning|afternoon|evening|time|summer|winter|spring|fall|season)\b)",
    re.IGNORECASE,
)

_WORD = re.compile(r"[^\W_][\w'+#-]*")
_MATH = re.compile(r"[\w^.()]+ ?(?:[-+*/^=<>] ?[\w^.()]+)+")
STOP_WORDS = frozenset(
    """a about above after again all also am an and any are as at be because been before
    being below between both but by can can't could did didn't do does doesn't doing don't
    done down during each few for from further going gonna got gotta had has have having he
    her here hers him his how how's i i'd i'll i'm i've if in into is isn't it it's its just
    know let let's like me mine more most much must my no nor not now of off ok okay on once
    only or other our ours out over own please pls really right same say she should so some
    such than thank thanks that that's the their them then there there's these they this
    those through to too under until up us very want wanna was we well were what what's
    whats when where where's which while who who's whom whose why will with would yeah yes
    you your yours actually maybe need think see looking way ways get use using used today
    tomorrow tonight yesterday current currently latest recent good best better great nice
    new thing things stuff something anything everything example examples summary tip tips
    detail details step steps code version answer explanation table pros cons difference
    differences idea ideas option options question questions info information overview
    breakdown work works working time quick another one ones lot made mean means happen
    happens""".split()
)
TASK_WORDS = frozenset(TASK_VERBS)


def topic_words(text: str) -> frozenset[str]:
    """What a clause is about: its content words, and each maths expression whole."""
    lowered = text.lower()
    found = {re.sub(r"\s", "", span) for span in _MATH.findall(lowered) if _is_math(span)}
    for raw in _WORD.findall(lowered):
        word = raw.strip("'-").removesuffix("'s")
        if len(word) >= 3 and word not in STOP_WORDS and word not in TASK_WORDS:
            found.add(word)
    return frozenset(found)


def _is_math(span: str) -> bool:
    return any(ch.isdigit() for ch in span) or "=" in span


def points_back(text: str) -> bool:
    """True when the clause leans on the one before it ("graph it", "which is faster")."""
    return _POINTS_BACK.search(_EMPTY_IT.sub(" ", text)) is not None
