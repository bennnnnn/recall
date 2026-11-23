"""Which question a slotted fact answers, held to the fact's own sentence.

A slot is destructive: a fact in one replaces every older fact in it (``writes_repository``),
and a held slot keeps an earlier chat's answer out (``pass_writes._filling_gaps``). The model
names the slot; the server keeps it only when the fact it labels answers that question. The
owner's memory filed "User earns an annual income of 200k" under name, so it replaced their
name, and test accounts held "User has an exam on Monday", "User owns a 2014 Honda Civic" and
"User's rent increased by $100" as where they live (2026-11-21/22).

Each slot's question is data (``_ASKS``), read in the fact's sentence: the memory model
writes every fact in English, in the third person, whatever language the user wrote in, so
the check reads the model's wording, never the user's. The name slot asks the parser that
already reads a fact for the user's name (``user_name.names_the_user``). A fact whose slot
fails is kept, in no slot: it adds up instead of replacing anything.

Two more readings use the same data:

- ``answer_frame``: the words that ask a slot's question ("name", "lives", "works"). A quote
  that shares only these with its fact does not give the answer: "my name" never states
  "User's name is Binne" (``grounding``).
- ``sensitive_slots``: the slots a fact answers whose answer the user must state about
  themselves (gender, age, religion, relationship), whether or not the model named a slot.
"""

from __future__ import annotations

import re

from app.modules.memory.schemas import memory_slot
from app.modules.memory.user_name import names_the_user

_FAVORITE = "favorite_"
_STEM = 4


# The fact's subject is the user ("User lives", "User's wife"), with adverbs between
# ("User now lives", "User recently moved"): "User's sister lives in Lisbon" is no home of
# theirs, and "User has a 7-year-old son" no age.
# "User is vegetarian and lives in Denver" answers it after a first clause about the user.
_SUBJECT = (
    r"^\s*(?:the )?user(?:'s)?\s+(?:is [^,;]*? and\s+)?"
    r"(?:(?:\w+ly|now|still|also|just|currently)\s+)*"
)
_DECADES = r"(?:\d0s|twenties|thirties|forties|fifties|sixties|seventies|eighties|nineties)"
_RELIGIONS = (
    r"christian\w*|muslim|islam\w*|jew|jewish|hindu\w*|buddhis\w*|sikh\w*|atheis\w*"
    r"|agnostic|orthodox|catholic\w*|protestant|evangelical|mormon|lds|baptist|lutheran"
    r"|methodist|pentecostal|adventist|anglican|quaker|jain\w*|baha'?i|shinto\w*|pagan|wiccan"
    r"|spiritual|religious"
)
_PARTNERS = r"wife|husband|partner|girlfriend|boyfriend|spouse|fianc\w*"


_JOB_VERBS = (
    r"works?|is working|worked|is (?:self-)?employed|is retired|retired|is unemployed"
    r"|runs|owns|manages|is the (?:owner|founder|ceo|manager)|founded|co-?founded"
)
# A word of the noun a job is named by: never one that ties the noun to something else, as
# "a fan of jazz", "an expert on wine" or "a mentor to new hires" do.
_NOUN_WORD = r"(?!(?:of|about|to|for|with|in|on|at|from|by|who|that|which|than|and)\b)[\w-]+"
# "User is a nurse", "User is an accountant at Deloitte", "User is a director of engineering
# at Stripe", "User is a nurse who works at Denver Health": the job named outright, the whole
# first clause ("User is a nurse and is 30"). An "of" is a title's only with its employer.
_JOB_NAMED = re.compile(
    rf"^\s*(?:the )?user is an? (?:{_NOUN_WORD} ){{0,3}}{_NOUN_WORD}"
    rf"(?:(?: of (?:{_NOUN_WORD} ){{0,2}}{_NOUN_WORD})? (?:at|for) [^,;]+?"
    rf"| who (?:{_JOB_VERBS})(?![\w-])[^,;]*?)?"
    r"(?=\.?\s*$|,| and )",
    re.IGNORECASE,
)
# The other questions a noun after "is a" answers: "a student", "a teenager", "a woman",
# "a Christian", "a widow" name no job.
_NOUN_SLOTS = ("school", "age", "gender", "religion", "relationship_status", "hometown")


def _about_user(body: str, *, flags: int = re.IGNORECASE) -> re.Pattern[str]:
    return re.compile(rf"{_SUBJECT}(?:{body})(?![\w-])", flags)


# What the opening of a fact that answers each question says.
_ASKS: dict[str, tuple[re.Pattern[str], ...]] = {
    "age": (
        _about_user(
            r"is (?:(?:a|an|about|around|nearly|almost|turning|now) )*\d{1,3}"
            r"(?:[ -]years?[ -]old|-year-old|(?=\s*(?:$|[.,;]|and\b)))"
            r"|(?:turns|turned|will turn) \d{1,3}|was born in \d{4}|age"
            rf"|is (?:\S+ ){{0,3}}?in (?:their|his|her) (?:early |late |mid-?)?{_DECADES}"
            r"|is (?:a |an )?teen(?:ager)?"
        ),
    ),
    "gender": (
        _about_user(
            r"(?:is|identifies as) (?:a |an )?(?:\S+ ){0,2}?(?:man|woman|male|female"
            r"|non-?binary|enby|trans(?:gender)?|genderqueer|genderfluid|agender)"
            r"|gender|pronouns"
        ),
    ),
    "home": (
        _about_user(
            r"lives?|is living|is based|resides|is residing|has moved|moved|has relocated"
            r"|relocated|is staying|stays|is located|home|city|town|address"
        ),
        # "User is in Toronto": a place, named in upper case ("User is in 10th grade" is not).
        re.compile(r"^\s*(?:[Tt]he )?[Uu]ser\s+is (?:now |currently )?in (?:the )?[A-Z]"),
    ),
    "hometown": (
        _about_user(
            r"is (?:originally )?from|comes from|grew up|was born|was raised|hometown"
            r"|is (?:a )?native (?:of|to)"
        ),
    ),
    "school": (
        _about_user(
            r"is (?:a |an )?(?:\S+ ){0,3}?(?:student|undergrad\w*|pupil|major|grader|schooler"
            # A year names a school's when nothing follows it ("a senior at NYU"); "a senior
            # engineer" is a job.
            r"|(?:freshman|sophomore|junior|senior)"
            r"(?=\s*(?:$|[.,;]|(?:at|in|of|and|who|year|this|from)\b)))"
            r"|is in (?:\S+ ){0,2}?(?:grade|year|class|form|school|college|university|uni)"
            r"|studies|is studying|attends|is attending|goes to|is enrolled"
            r"|(?:is taking|takes) (?:\S+ ){0,3}?(?:class|classes|course|courses|module)"
            r"|is doing (?:\S+ ){0,3}?(?:degree|course|gcses?|a-levels?|ged|phd|masters?)"
            r"|is majoring|majors?|school|university|college"
        ),
    ),
    "job": (_about_user(rf"{_JOB_VERBS}|job|occupation|profession|career|role|position|employer"),),
    "relationship_status": (
        _about_user(
            r"is (?:\S+ )?(?:married|single|dating|engaged|divorced|separated|widowed"
            r"|a widow(?:er)?|in a (?:\S+ )?relationship|partnered)"
            rf"|(?:has|had) an? (?:\S+ )?(?:{_PARTNERS})|got married|married"
            r"|dates|is seeing|relationship"
        ),
        # "User's wife is named Hana": the partner is the user's own, named straight after.
        re.compile(rf"^\s*(?:the )?user's (?:current |new )?(?:{_PARTNERS})(?![\w-])", re.I),
    ),
    "religion": (
        _about_user(
            r"(?:is|identifies as) (?:(?:a|an|very|devout|practicing|practising|non-practicing"
            rf"|observant|not) )*(?:{_RELIGIONS})"
            rf"|(?:practices|follows) (?:(?:their|his|her|the) )?(?:{_RELIGIONS}|faith|religion)"
            r"|believes in (?:god|allah)|religion|faith|prays"
            r"|(?:attends|goes to) (?:church|mosque|temple|synagogue)"
        ),
    ),
}
_FAVORITE_ASKS = re.compile(
    r"\b(?:favou?rites?|fav|faves?|loves? most|likes? best|best-loved)\b", re.IGNORECASE
)

# The words that ask each question but are not its answer. The questions whose words are
# the answer (gender, religion, relationship) have none: "married" holds "User is married".
_FRAME: dict[str, frozenset[str]] = {
    "name": frozenset(
        "name names named called call goes go nickname preferred first full last given legal "
        "real".split()
    ),
    "age": frozenset("years year old aged age".split()),
    "home": frozenset(
        "lives live living based resides reside residing moved moving relocated located "
        "stays stay staying home currently now".split()
    ),
    "hometown": frozenset("from grew up born raised hometown native originally".split()),
    "school": frozenset(
        "student students studies study studying attends attending enrolled currently".split()
    ),
    "job": frozenset(
        "works work working worked job employed employer employment career profession "
        "occupation position role currently".split()
    ),
}
_FAVORITE_FRAME = frozenset("favorite favourite favorites favourites fav fave faves".split())

# Answers the user must state about themselves: a pick ("female" for a voice), a level or a
# guess from a name is none of them (``grounding``).
SENSITIVE_SLOTS = frozenset(("gender", "age", "religion", "relationship_status"))

# How the assistant asks the user one of those questions, in English: a bare "34" answers
# "How old are you?"; "female" answers no "Would you like a male or a female voice?".
_ASKED: dict[str, re.Pattern[str]] = {
    "age": re.compile(
        r"\b(?:how old are you|your age|what age are you|are you (?:over|under) \d+)\b",
        re.IGNORECASE,
    ),
    "gender": re.compile(
        r"\b(?:your gender|your pronouns|(?:what )?do you identify as"
        r"|are you (?:a )?(?:man|woman|male|female|non-?binary))\b",
        re.IGNORECASE,
    ),
    "religion": re.compile(
        r"\b(?:your (?:religion|faith)|what religion|are you (?:religious|spiritual|"
        r"christian|muslim|jewish|hindu|buddhist|catholic|orthodox|atheist|agnostic)"
        r"|do you (?:practi[cs]e|follow) (?:a |any )?(?:religion|faith))\b",
        re.IGNORECASE,
    ),
    "relationship_status": re.compile(
        r"\b(?:are you (?:married|single|dating|engaged|divorced|seeing (?:someone|anyone)"
        r"|in a relationship)|your (?:relationship|partner|wife|husband|girlfriend|boyfriend"
        r"|spouse)|do you have a (?:partner|wife|husband|girlfriend|boyfriend|spouse))\b",
        re.IGNORECASE,
    ),
}


def _thing_words(slot: str) -> list[str]:
    return [part for part in slot.removeprefix(_FAVORITE).split("_") if part]


def _names_thing(word: str, thing: str) -> bool:
    """Four shared letters make one word: "colour" for "color", "movies" for "movie"."""
    return word == thing or (len(thing) >= _STEM and word[:_STEM] == thing[:_STEM])


def _says_favorite(slot: str, fact: str) -> bool:
    """ "User's favorite colour is blue" answers favorite_color: the thing is named too."""
    if not _FAVORITE_ASKS.search(fact):
        return False
    words = re.findall(r"\w+", fact.casefold())
    return all(any(_names_thing(word, thing) for word in words) for thing in _thing_words(slot))


def answers_slot(slot: str, fact: str) -> bool:
    """Whether ``fact`` (the model's English sentence) answers the slot's question."""
    if slot == "name":
        return names_the_user(fact)
    if slot.startswith(_FAVORITE):
        return _says_favorite(slot, fact)
    if slot == "job" and _names_job(fact):
        return True
    return any(pattern.search(fact) for pattern in _ASKS.get(slot, ()))


def _names_job(fact: str) -> bool:
    """ "User is a nurse": a noun after "is a" that no other question claims."""
    named = _JOB_NAMED.match(fact)
    return named is not None and not any(
        answers_slot(other, named.group(0)) for other in _NOUN_SLOTS
    )


def answered_slot(raw: object, fact: str) -> str | None:
    """The slot to file ``fact`` under: the model's, when the fact answers it, else None."""
    slot = memory_slot(raw)
    if slot is None or not answers_slot(slot, fact):
        return None
    return slot


def frame_words(fact: str, slot: str | None) -> frozenset[str]:
    """The words of ``fact`` (case folded) that ask its question rather than answer it.

    A fact that names the user is read as the name slot whatever the model labelled it: the
    name must be in the quote either way.
    """
    frame: set[str] = set()
    if slot is not None:
        frame |= _FRAME.get(slot, frozenset())
    if slot != "name" and names_the_user(fact):
        frame |= _FRAME["name"]
    words = set(re.findall(r"\w+", fact.casefold()))
    found = words & frame
    if slot is not None and slot.startswith(_FAVORITE):
        things = _thing_words(slot)
        found |= {
            word
            for word in words
            if word in _FAVORITE_FRAME or any(_names_thing(word, thing) for thing in things)
        }
    return frozenset(found)


def sensitive_slots(fact: str, slot: str | None) -> frozenset[str]:
    """The sensitive questions ``fact`` answers: its own slot, and any it reads as."""
    found = {name for name in SENSITIVE_SLOTS if answers_slot(name, fact)}
    if slot in SENSITIVE_SLOTS:
        found.add(slot)
    return frozenset(found)


def asked_about_themselves(slots: frozenset[str], question: str) -> bool:
    """Whether the assistant's ``question`` asked the user every one of these questions."""
    return bool(slots) and all(name in _ASKED and _ASKED[name].search(question) for name in slots)
