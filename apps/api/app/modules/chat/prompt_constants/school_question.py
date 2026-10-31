"""A school exercise, said beside the message: the textbook's answer, at its level.

A Class 8 physical science book's exercises (2026-10-30) got answers a student could not
hand in: "That's a riddle dressed as a question", a multiple-choice answer that changed
its mind and blamed the textbook, electroplating aluminium sent to molten cryolite at
1000 °C, a definition answered from a search that cited a YouTube comment, and offers of
more at the end. The note nearest the message is the one a small model keeps to.

A Class 9 book in every subject (2026-10-30) showed the first reader was that book's
phrases: it knew 10 of 129 exercises. An exercise is now read from the shapes every
textbook prints, whatever the subject:

- options to choose from: a stem, then (a) to (d) or (i) to (iv), on their own lines, or
  short, or after "which of the following" / "choose";
- an assertion and its reason, a blank to fill, or two or more labelled parts;
- an exercise's order: "Differentiate between", "Identify", "Justify", "Arrange the
  following", "Calculate", "Give reasons", "Fill in the blanks";
- a scenario about a student, a class, a farmer or a researcher, then a question;
- a closing order ("…? Explain."), an assessment code ("(AS1)"), a textbook's phrase.

Never from words anyone uses ("Explain decorators", "Define success.", "Plan a trip
covering a) Rome b) …", "Calculate my BMI", a Markdown checklist's "[ ]"): a message that
is anyone's own matter (``question_kinds.anyones``) is no exercise, whatever its shape.
Any other question about the world gets the lighter factual note.
"""

from __future__ import annotations

import re

from app.modules.chat.prompt_constants.question_kinds import (
    anyones,
    is_factual_question,
    is_science_question,
    mentions_science,
    names_or_news,
)
from app.services.question_parts import labelled_parts

# "a) …", "(b) …", "C. …", "[D] …", "(iii) …": an option's label, after a space or the start.
_OPTION = re.compile(r"(?:^|(?<=[\s\[(]))\(?([a-dA-D]|i{1,3}|iv)[).\]]\s+", re.MULTILINE)
_LETTERS = ("abcd", ("i", "ii", "iii", "iv"))
_JOINED_LABELS = re.compile(r"(?:,|\band)\s*\(?(?:b|ii)\)\s", re.IGNORECASE)
_CHOOSE = re.compile(
    r"\b(?:which\s+(?:one\s+)?of\s+the\s+following|choose|select|pick\s+out|tick|correct\s+"
    r"(?:option|answer|statement|explanation|sequence|order|pair))\b",
    re.IGNORECASE,
)
# A request for every item, not a choice of one: "Plan a trip covering a) Rome b) …",
# "opening hours of a) the Louvre b) …", "Compare the specs of a) …".
_ALL_ITEMS = re.compile(
    r"^\s*(?:plan|write|compare|make|create|draft|list|give|generate|suggest|rank|rate|sort"
    r"|summari[sz]e|help|pick|choose|recommend|name)\b(?!\s+the\s+correct)"
    r"|\b(?:of|for|between|covering|about|these|each|both|all)\s*:?\s*$",
    re.IGNORECASE,
)
_CODE = re.compile(r"\(\s*AS\s*\d\s*\)|\[[ \t]+\]\s*(?:$|\(?[aA][).])", re.MULTILINE)
# An exercise's own order, opening the message or a sentence of it. "Define success." and
# "Explain decorators" are anyone's, so define, describe, explain and list are not here:
# the factual note has them.
_OPENING = re.compile(
    r"(?:^|[.?!:]\s+)(?:\d{1,2}[.)]\s*)?(?:distinguish\s+between|differentiate\s+between"
    r"|give\s+(?:two|three|four|five|any\s+two|any\s+three)\s+examples?\s+each"
    r"|write\s+the\s+differences?\s+between|identify|justify|indicate|illustrate"
    r"|arrange\s+the|classify\s+the\s+following|match\s+the\s+following"
    r"|fill\s+in\s+the\s+blanks?|choose\s+the\s+correct|tick|state\s+whether"
    r"|calculate|determine|estimate|predict|give\s+reasons?\s+(?:why|for\s+the)"
    r"|complete\s+the\s+(?:table|following)|verify\s+(?:whether|that|the)"
    r"|write\s+(?:down\s+)?the\s+(?:formulae?|chemical|balanced|electronic|symbols?|correct)"
    # "Write one equation each for…", "Write a balanced equation for…".
    r"|write\s+(?:down\s+)?(?:an?|one|two|three)\s+(?:\w+\s+){0,2}(?:equations?|formulae?)"
    r"|write\s+a\s+short\s+note\s+on|give\s+an\s+account\s+of|mention\s+(?:two|three|any|the)"
    r"|what\s+is\s+meant\s+by|(?:change|correct|rewrite|punctuate)\s+the\s+following"
    r"|use\s+the\s+following\s+words|name\s+the\s+following|give\s+reasons?(?=\s*:)|outline\s+the"
    r"|account\s+for|balance\s+the|convert)\b",
    re.IGNORECASE,
)
_ASSERTION = re.compile(r"\bassertion\b.*\breason\b", re.IGNORECASE | re.DOTALL)
_BLANK = re.compile(r"_{3,}|…{2,}|\.{6,}")
# Someone a textbook's scenario is about: "A student said", "Two students, Renu and
# Rohit", "A farmer wants", "Vibha claims to her friend that, “…”".
_SCENARIO = re.compile(
    r"\b(?i:a|an|the|two|three|some)\s+(?:\w+\s+)?(?:students?|girl|boy|teacher|farmer"
    r"|researchers?|scientists?|class(?:mates)?|classroom)\b"
    r"|\b[A-Z][a-z]+\s+and\s+[A-Z][a-z]+\s+(?:were|are|observed|noticed|had)\b"
    r"|\b[A-Z][a-z]+\s+(?:claims?|argues|counter\s+argues|says|said)\b[^\"\u201c\n]{0,40}[\"\u201c]",
)
# An exercise's verb: what a book asks a student to do.
_ORDER = re.compile(
    r"\b(?:explain|justify|predict|suggest|identify|discuss|calculate|find|determine"
    r"|estimate|verify|obtain|express|state|give\s+reasons?|provide|what\s+do\s+you\s+think)\b",
    re.IGNORECASE,
)
# A quantity a word problem gives: "24 m/s", "50 g", "6 s", "5 minutes", "70%".
_QUANTITY = re.compile(
    r"\d(?:[\d,]*\d)?(?:\.\d+)?\s*(?:%|°\s*[CF]\b|(?:km|cm|mm|m|kg|g|mg|s|min|minutes?|h|hours?"
    r"|seconds?|N|J|kJ|W|kW|Hz|kHz|K|Pa|L|mL|u|mol|V|A|Ω)"
    r"(?:\s*(?:/|per)\s*(?:s²|s\^?2|s|h|m³|m\^?3|L|mol))?\b)"
)
_COMPUTE = re.compile(r"\b(?:calculate|compute|find|determine|work\s+out)\b", re.IGNORECASE)
_CLOSING = re.compile(
    r"[.?!]\s*(?:explain(?:\s+why)?|justify|discuss|(?:give|specify)\s+reasons?)"
    r"(?P<yours>\s+(?:for\s+)?your\s+answer)?\s*[.?!]?\s*$",
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

# A worked answer that states its result first wrote "The ratio is 1 : 5" over working
# that found 4 : 5, and "0.054 s" over a box of 0.015 s (2026-10-30); told to work first
# beside "open with the answer", it opened "The ratio is 2 : 5". A calculation's opening
# is its working.
WORK_FIRST = (
    "A calculation is the exception to answering first: it opens with its working (what "
    "is given, the formula, the substitution) and states its result once, at the end; "
    "never write a number before you have worked it out, and never think aloud (no "
    "'actually', 'wait' or 'let me recheck')."
)
# Told "stay at that level" and "no specialist detail", a Class 10 book's "Which signals
# are disrupted by a spinal cord injury?" got spinal tracts and T1-L2 outflow, and "the
# function of receptors" myasthenia gravis (2026-10-30): a depth the model reads from the
# question alone needs its edge named.
TEXTBOOK_DEPTH = (
    "Go only as deep as a school textbook does: use the terms the question uses or a "
    "textbook would, and no clinical, research or university detail (named pathways, "
    "receptors, diseases, molecular mechanisms, bonding theory) unless the question asks "
    "for it; no side claim you are unsure of."
)
# A factual question may be an adult's ("How do mRNA vaccines work?"): its depth follows its
# own words, and only a question in a school book's words is held to a school book's.
MATCHED_DEPTH = (
    "Go as deep as the question's own words: a question worded like a school book's gets a "
    "school book's answer, with no clinical, research or university detail (named pathways, "
    "receptors, diseases, molecular mechanisms) it did not ask for; one in specialist words "
    "may get a specialist's. No side claim you are unsure of."
)
SCHOOL_QUESTION_NOTE = (
    "This message is a school exercise. Answer it as the textbook expects, for the "
    "student who asked, at the level the question is written, from what the textbook "
    "teaches: open with the answer itself in plain words, using "
    "the textbook's terms, then a short reason or two to four everyday examples. "
    + WORK_FIRST
    + " "
    + TEXTBOOK_DEPTH
    + " No history or regional trivia it did not ask for. Take the question as written: "
    "never call it a trick or a riddle, never dispute its wording, its options or the "
    "textbook, and never ask "
    "where it came from. Answer every part it asks, in order. End when the answer is "
    "complete, with no offer of more."
)
_CHOICE_NOTE = (
    " It asks you to choose: name the one correct option, its label and words, first, "
    "then one or two lines on why; never change the option partway, name two, or say "
    "none is correct."
)
FACTUAL_QUESTION_NOTE = (
    "This is a factual question. Give the standard answer a good textbook gives, first, "
    "in plain words at the level the question is asked, then a short reason or a few "
    "examples. " + WORK_FIRST + " " + MATCHED_DEPTH + " Take the question as written: "
    "never open by disputing it, correcting its wording or calling it a trick, and keep to "
    "what it asks. End when the answer is complete, with no offer of more."
)


def _options(text: str) -> tuple[str, list[str], bool] | None:
    """The stem, the option texts, and whether each option opens its own line, when
    ``text`` has options labelled in order: a), b), c) or (i), (ii), (iii)."""
    found = list(_OPTION.finditer(text))
    labels = [match.group(1).lower() for match in found]
    for sequence in _LETTERS:
        for start in range(len(labels) - 2):
            if tuple(labels[start : start + 3]) != tuple(sequence[:3]):
                continue
            chosen = found[start:]
            ends = [match.start() for match in chosen[1:]] + [len(text)]
            texts = [text[match.end() : end] for match, end in zip(chosen, ends, strict=False)]
            lines = all(text[: match.start()].rstrip(" \t").endswith("\n") for match in chosen[:3])
            return text[: chosen[0].start()], texts, lines
    return None


def _choice(text: str) -> bool:
    """Options to choose one of, about nothing that changes or is a matter of taste."""
    read = _options(text)
    if read is None:
        return False
    stem, texts, own_lines = read
    # "what is its (i) distance, (ii) displacement and (iii) speed?" lists asks, and an
    # option that is itself a question, or a blank to fill, is a part.
    if _JOINED_LABELS.search(text) or _BLANK.search(text) or any("?" in o for o in texts[:-1]):
        return False
    asked = (
        all(len(option.split()) <= 8 for option in texts)
        or _CHOOSE.search(stem) is not None
        or (own_lines and stem.rstrip().endswith(("?", ":", ".")))
    )
    return (
        asked and len(stem.split()) >= 3 and _ALL_ITEMS.search(stem) is None and not anyones(text)
    )


def _closes_as_exercise(text: str) -> bool:
    """An exercise's closing order ("… Explain."). "Explain your answer." closes anyone's
    opinion too ("Was Napoleon a good leader? Explain your answer."): only about science."""
    closing = _CLOSING.search(text)
    if closing is None or len(text.split()) < 8:
        return False
    return closing.group("yours") is None or mentions_science(text)


def is_school_exercise(query: str) -> bool:
    text = query.strip()
    if _choice(text):
        return True
    if anyones(text):
        return False
    if _CODE.search(text) or _closes_as_exercise(text):
        return True
    if _TEXTBOOK.search(text) or _ASSERTION.search(text) or _BLANK.search(text):
        return True
    if _OPENING.search(text):
        return True
    if _ORDER.search(text) is None and "?" not in text:
        return False
    quantities = len(_QUANTITY.findall(text))
    return bool(
        (labelled_parts(text) and (_ORDER.search(text) or quantities or mentions_science(text)))
        or _SCENARIO.search(text)
        or quantities >= 2
        or (quantities == 1 and _COMPUTE.search(text))
    )


# A verdict to reason out: "Who is correct?", "Which element is more reactive?", "State
# whether the claim is correct". Answered first and reasoned after, it opened "Rohan is
# correct" over a body that showed Rajiv was, and "A is more reactive" over the trend that
# made B so (2026-10-30).
_VERDICT = re.compile(
    r"\bwho\s+is\s+(?:correct|right)\b"
    r"|\bwhich\s+(?:\w+\s+){0,3}(?:is|are|will\s+be|would\s+be|has)\s+(?:more|less|most|least"
    r"|greater|smaller|larger|higher|lower|correct|incorrect|true|false)\b"
    r"|\b(?:correct|true|valid)\s+or\s+(?:not|false|incorrect)\b|\bstate\s+whether\b"
    r"|\bcritically\s+examine\b|\bwhat\s+do\s+you\s+think\s+about\s+this\s+statement\b"
    # A class to read from clues: "Which type of pollination happens in these flowers?"
    r"|\bwhich\s+(?:type|kind|group|category|class|kingdom|phylum)\s*(?:\(s\)|s)?\s+of\b",
    re.IGNORECASE,
)


def needs_reasoned_choice(query: str) -> bool:
    """An exercise's choice to reason out first: its options, its assertion and reason,
    or a verdict on a textbook scenario ("Two students… Who is correct?"). An everyday
    "which is more reliable" stays on its own lane."""
    text = query.strip()
    if not is_school_exercise(text):
        return False
    verdict = _SCENARIO.search(text) is not None and _VERDICT.search(text) is not None
    return bool(_choice(text) or _ASSERTION.search(text) or verdict)


def has_nothing_to_look_up(query: str) -> bool:
    """An exercise in a textbook's own form (options, an assertion and its reason, a blank,
    an assessment code), or a plain science question: a search only finds worse answers
    ("…is called its a) Ignition temperature b) …" was answered from a YouTube comment)."""
    text = query.strip()
    if is_science_question(text):
        return True
    if anyones(text):
        return False
    # A science exercise written as an order: "Differentiate between RER and SER", "Explain
    # osmosis with an example".
    if is_school_exercise(text) and mentions_science(text) and not names_or_news(text):
        return True
    return in_textbook_form(text)


def in_textbook_form(query: str) -> bool:
    """An exercise only a textbook prints this way: options to choose from, an assertion and
    its reason, a blank to fill, an assessment code; never anyone's own matter."""
    text = query.strip()
    if anyones(text):
        return False
    return bool(
        _choice(text) or _ASSERTION.search(text) or _BLANK.search(text) or _CODE.search(text)
    )


def school_question_hint(query: str) -> str | None:
    """The note for a school exercise, or None."""
    if is_school_exercise(query):
        text = query.strip()
        chooses = _choice(text) or _ASSERTION.search(text) is not None
        return SCHOOL_QUESTION_NOTE + (_CHOICE_NOTE if chooses else "")
    return None


def question_hint(query: str) -> str | None:
    """The note beside a message: a school exercise's, a factual question's, or None."""
    return school_question_hint(query) or (
        FACTUAL_QUESTION_NOTE if is_factual_question(query) else None
    )
