"""A school exercise, said beside the message: the textbook's answer, at its level.

A Class 8 physical science book's exercises (2026-10-30) got answers a student could not
hand in: "That's a riddle dressed as a question", "Where did this question come from?",
a multiple-choice answer that changed its mind and blamed the textbook, an umbrella
question argued with expected-value tables, electroplating aluminium sent to molten
cryolite at 1000 °C, a definition answered from a search that cited a YouTube comment,
and offers of more at the end. The reply's level follows the question's; the note
nearest the message is the one a small model keeps to.

An exercise is read from a textbook's own shapes only, never from words anyone uses
("Explain decorators with an example", "Define success.", "Write a short note to my
landlord", a Markdown checklist's "[ ]", "Should I refinance? Explain why.", "Which is
better for a beginner: a) Python b) Rust"). Every other question still gets the general
rule (``format._UNIVERSAL_FORMAT_CORE``): the standard answer first, never disputed.

- a multiple-choice question: a stem, then short options a, b, c, and nothing current;
- an assessment code ("(AS1)") or an answer blank ("[ ]" before the options);
- an exercise's order: "Give two examples each for", "Distinguish between";
- a closing order after a question that is not about the asker ("…? Explain.");
- a textbook's phrase: "with suitable examples", "in our daily life", "Do you agree with
  the statement “…”".
"""

from __future__ import annotations

import re

# "a) …", "(b) …", "C. …", "[D] …": an option's letter, after a space or the start.
_OPTION = re.compile(r"(?:^|(?<=[\s\[(]))\(?([a-dA-D])[).\]]\s+")
_OWN = re.compile(r"\b(?:i|i'm|my|me|we|our|us)\b", re.IGNORECASE)
# A request for every item, not a choice of one: "Plan a trip covering a) Rome b) …",
# "opening hours of a) the Louvre b) …", "Compare the specs of a) …".
_ALL_ITEMS = re.compile(
    r"^\s*(?:plan|write|compare|make|create|draft|list|give|generate|suggest|rank|rate|sort"
    r"|summari[sz]e|help|pick|choose|recommend|name)\b"
    r"|\b(?:of|for|between|covering|about|these|each|both|all)\s*:?\s*$",
    re.IGNORECASE,
)
# A matter of taste, not a fact a book states: "Which is better for a beginner", "Which
# toppings go well together", "Which sounds more professional".
_TASTE = re.compile(
    r"\b(?:(?:better|best)\s+(?:for|than|to|choice|option|pick)|prefer\w*|favou?rite"
    r"|sounds\s+(?:more|better|nicer|best)|go\s+well|should|would\s+you|recommend\w*"
    r"|nicer|cuter|cooler|tastier)\b",
    re.IGNORECASE,
)
# What changes, so no textbook holds it: news, prices, people in office, travel.
_CURRENT = re.compile(
    r"\b(?:current(?:ly)?|now|today|latest|newest|this\s+(?:week|year|month)|price|cost|stocks?"
    r"|pric\w*|ceo|president|prime\s+minister|airlines?|flights?|visa|open(?:ing)?\s+hours"
    r"|weather"
    r"|buy|cheapest)\b",
    re.IGNORECASE,
)
_CODE = re.compile(r"\(\s*AS\s*\d\s*\)|\[[ \t]+\]\s*(?:$|\(?[aA][).])", re.MULTILINE)
# "Define success." and "Give two examples of cover letter openings" are anyone's: only
# an exercise's own wording ("Give two examples each for …").
_OPENING = re.compile(
    r"^\s*(?:\d{1,2}[.)]\s*)?(?:distinguish\s+between|differentiate\s+between"
    r"|give\s+(?:two|three|four|five|any\s+two|any\s+three)\s+examples?\s+each"
    r"|write\s+the\s+differences?\s+between)\b",
    re.IGNORECASE,
)
# Code, an error or a programming word: a developer's question, whatever its shape.
_CODE_TALK = re.compile(
    r"`|\b[a-z]+[A-Z]\w*\b|\b[A-Z][a-z]+[A-Z]\w*\b|\b(?i:error|exception|function|code"
    r"|javascript|typescript|python|java|sql|api|bug|compile\w*)\b"
)
_CLOSING = re.compile(
    r"[.?!]\s*(?:explain(?:\s+why)?|justify|discuss|(?:give|specify)\s+reasons?)\s*[.?!]?\s*$",
    re.IGNORECASE,
)
_TEXTBOOK = re.compile(
    r"\bwith\s+suitable\s+examples?\b|\bin\s+(?:our|your)\s+daily\s+life\b"
    # The statement in quotes, then an exercise's order: "… “friction is good and evil”.
    # Explain with examples."; "Do you agree with the statement “remote work kills …”?" is
    # an opinion asked.
    r"|\bdo\s+you\s+(?:agree|support)\b.*\bstatement\s*[.:]?\s*[\"\u201c'\u2018].*"
    r"\b(?:explain|justify|give\s+reasons?|with\s+examples?)\b",
    re.IGNORECASE | re.DOTALL,
)

SCHOOL_QUESTION_NOTE = (
    "This message is a school exercise. Answer it as the textbook expects, for the "
    "student who asked, at the level the question is written, from what the textbook "
    "teaches (no web search for it): open with the answer itself in plain words, using "
    "the textbook's terms, then a short reason or two to four everyday examples. Stay at "
    "that level: no university detail, history or regional trivia it did not ask for, and "
    "no side claim you are unsure of. Take the question as written: never call it a trick "
    "or a riddle, never dispute its wording or the textbook, and never ask where it came "
    "from. End when the answer is complete, with no offer of more."
)
_CHOICE_NOTE = (
    " It is multiple choice: name the one correct option, its letter and words, first, "
    "then one or two lines on why; never change the option partway or name two."
)


def _multiple_choice(text: str) -> bool:
    """A stem, then options a, b, c in order, each a few words: a question with one
    answer among them, about nothing that changes."""
    options = list(_OPTION.finditer(text))
    letters = "".join(match.group(1).lower() for match in options)
    start = letters.find("abc")
    if start < 0:
        return False
    stem = text[: options[start].start()]
    ends = [match.start() for match in options[start + 1 :]] + [len(text)]
    texts = [text[match.end() : end] for match, end in zip(options[start:], ends, strict=False)]
    return (
        len(stem.split()) >= 3
        and _OWN.search(stem) is None
        and _ALL_ITEMS.search(stem) is None
        and _TASTE.search(stem) is None
        and _CURRENT.search(text) is None
        and all(len(option.split()) <= 8 for option in texts)
    )


def _closing_order(text: str) -> bool:
    """ "…? Explain." after a question of eight words or more, not about the asker or code."""
    return (
        _CLOSING.search(text) is not None
        and len(text.split()) >= 8
        and _OWN.search(text) is None
        and _CODE_TALK.search(text) is None
    )


def is_school_exercise(query: str) -> bool:
    text = query.strip()
    return bool(
        _multiple_choice(text)
        or _CODE.search(text)
        or _OPENING.search(text)
        or _closing_order(text)
        or _TEXTBOOK.search(text)
    )


# A general science question asked plainly: "Why don't cooking pans have metal handles?",
# "Why does the image in a plane mirror suffer lateral inversion?". The rerun of the same
# book (2026-10-30) still opened "Most pans actually do have metal handles" and "it
# doesn't, really": a textbook answer is the one anyone asking it needs first.
_SCIENCE = re.compile(
    r"\b(?:forces?|friction|pressure|gravity|gravitational|weight|motion|speed|velocity"
    r"|accelerat\w+|energy|heat|temperature|sound|pitch|vibrat\w+|echo|loudness|noise"
    r"|light|mirrors?|reflect\w*|refract\w*|lens|shadow|image|magnet\w*|electric\w*"
    r"|current|circuit|charged?|conductors?|insulators?|electrolyt\w+|electroplat\w+"
    r"|metals?|non-?metals?|alloys?|rust\w*|corrosion|oxides?|acids?|bases?|salts?|plastics?"
    r"|thermoplastics?|fibres?|fibers?|nylon|polyester|rayon|fuels?|coal|petroleum"
    r"|combust\w+|flames?|ignition|burn\w*|oxygen|carbon|hydrogen|atoms?|molecules?"
    r"|elements?|compounds?|planets?|stars?|pole\s+star|moon|orbit\w*|satellites?|eclipse"
    r"|earthquakes?|lightning|thunder\w*|evaporat\w+|condens\w+|boiling|melting|density"
    r"|malleab\w+|ductil\w+|fossil|phosphorus|sulph\w+|sulf\w+|sodium|copper|iron|zinc"
    r"|alumin\w+|magnesium|calcium|mercury)\b",
    re.IGNORECASE,
)
_PLAIN_QUESTION = re.compile(
    r"^\s*(?:why|how|what|which|is|are|does|do|can|could|would|will|should|explain)\b",
    re.IGNORECASE,
)
_PERSONAL = re.compile(r"\b(?:i|i'm|i've|my|me|mine)\b", re.IGNORECASE)

SCIENCE_QUESTION_NOTE = (
    "This is a general science question. Give the explanation a good science textbook "
    "gives, first, in plain words at the level the question is asked, then a short reason "
    "or a few everyday examples. Take the question as written: never open by disputing "
    "it, correcting its wording or calling it a trick, and keep to what it asks: no "
    "specialist detail, regional examples or side claims you are unsure of. End when the "
    "answer is complete, with no offer of more."
)


def is_science_question(query: str) -> bool:
    """A short question about a science idea, not about the asker, code or anything current."""
    text = query.strip()
    return (
        len(text.split()) <= 45
        and _PLAIN_QUESTION.search(text) is not None
        and _SCIENCE.search(text) is not None
        and _PERSONAL.search(text) is None
        and _CODE_TALK.search(text) is None
        and _CURRENT.search(text) is None
        and _TASTE.search(text) is None
    )


def school_question_hint(query: str) -> str | None:
    """The note for a school exercise, or for a plain science question, or None."""
    if is_school_exercise(query):
        return SCHOOL_QUESTION_NOTE + (_CHOICE_NOTE if _multiple_choice(query.strip()) else "")
    return SCIENCE_QUESTION_NOTE if is_science_question(query) else None
