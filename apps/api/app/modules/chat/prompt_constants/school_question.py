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
covering a) Rome b) …", "Which is better for a beginner: a) Python b) Rust", a Markdown
checklist's "[ ]"): a message about the asker, code, anything current or a matter of
taste is no exercise. Any other question about the world gets the lighter factual note.
"""

from __future__ import annotations

import re

from app.modules.chat.prompt_constants.coding import has_code_syntax
from app.modules.chat.prompt_constants.conversation import is_social_opener
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
# The asker: "I", "my", "me". Not "(i)", a part's label, and not a book's "we observe".
_OWN = re.compile(r"(?<!\()\b(?:i(?!\))|i'm|i've|my|me)\b", re.IGNORECASE)
# A request for every item, not a choice of one: "Plan a trip covering a) Rome b) …",
# "opening hours of a) the Louvre b) …", "Compare the specs of a) …".
_ALL_ITEMS = re.compile(
    r"^\s*(?:plan|write|compare|make|create|draft|list|give|generate|suggest|rank|rate|sort"
    r"|summari[sz]e|help|pick|choose|recommend|name)\b(?!\s+the\s+correct)"
    r"|\b(?:of|for|between|covering|about|these|each|both|all)\s*:?\s*$",
    re.IGNORECASE,
)
# A matter of taste, not a fact a book states: "Which is better for a beginner", "Which
# toppings go well together", "Which sounds more professional".
_TASTE = re.compile(
    r"\b(?:(?:better|best)\s+(?:for|than|to|choice|option|pick)|prefer\w*|favou?rite"
    r"|sounds\s+(?:more|better|nicer|best)|go\s+well|should\s+(?:i|we)"
    r"|would\s+you\s+(?:rather|prefer|recommend|choose|pick|buy|use)"
    r"|recommend\w*|nicer|cuter|cooler|tastier"
    # "What is the best country", not "the best conductor of heat".
    r"|(?:best|worst)\s+(?!conductors?|insulators?|examples?|answer|options?|describes|explains)"
    r"\w+)\b",
    re.IGNORECASE,
)
# What changes, so no textbook holds it: news, prices, people in office, travel.
_CURRENT = re.compile(
    r"\b(?:current(?:ly)?|right\s+now|as\s+of\s+now|today|latest|newest|this\s+(?:week|year|month)|price|cost|stocks?"
    r"|pric\w*|ceo|president|prime\s+minister|airlines?|flights?|visa|open(?:ing)?\s+hours"
    r"|weather|buy|cheapest|tomorrow|tonight|yesterday|this\s+weekend|next\s+week|who\s+won"
    r"|last\s+(?:\w+\s+)?(?:cup|final|election|year|week|month|night|season|match|game))\b|\$\d",
    re.IGNORECASE,
)
_CODE = re.compile(r"\(\s*AS\s*\d\s*\)|\[[ \t]+\]\s*(?:$|\(?[aA][).])", re.MULTILINE)
# Code, an error or a programming word: a developer's question, whatever its shape.
# A chemical formula (NaHCO3, CuSO4) is a camel-cased word too, and no code.
_CODE_TALK = re.compile(
    r"`|\b(?![A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)+\b|[kmMGµ][A-Z]\w?\b)(?:[a-z]+[A-Z]\w*|[A-Z][a-z]+[A-Z]\w*)\b"
    r"|\b(?i:error|exception|code|javascript|typescript|python|java|sql|api|bug|compile\w*"
    r"|emails?)\b"
)
# An exercise's own order. "Define success." and "Explain decorators" are anyone's, so
# define, describe, explain and list are not here: the factual note has them.
_OPENING = re.compile(
    r"^\s*(?:\d{1,2}[.)]\s*)?(?:distinguish\s+between|differentiate\s+between"
    r"|give\s+(?:two|three|four|five|any\s+two|any\s+three)\s+examples?\s+each"
    r"|write\s+the\s+differences?\s+between|identify|justify|indicate|illustrate"
    r"|arrange\s+the|classify\s+the\s+following\s+(?!emails?)|match\s+the\s+following"
    r"|fill\s+in\s+the\s+blanks?|choose\s+the\s+correct|tick|state\s+whether"
    r"|calculate|determine|estimate|predict|give\s+reasons?\s+(?:why|for\s+the)"
    r"|complete\s+the\s+(?:table|following)|verify\s+(?:whether|that|the)"
    r"|write\s+(?:down\s+)?the\s+(?:formulae?|chemical|balanced|electronic|symbols?|correct))\b",
    re.IGNORECASE,
)
_ASSERTION = re.compile(r"\bassertion\b.*\breason\b", re.IGNORECASE | re.DOTALL)
_BLANK = re.compile(r"_{3,}|…{2,}|\.{6,}")
# Someone a textbook's scenario is about: "A student said", "Two students, Renu and
# Rohit", "A farmer wants", "A researcher placed".
_SCENARIO = re.compile(
    r"\b(?i:a|an|the|two|three|some)\s+(?:\w+\s+)?(?:students?|girl|boy|teacher|farmer"
    r"|researchers?|scientists?|class(?:mates)?|classroom|friends?)\b"
    r"|\b[A-Z][a-z]+\s+and\s+[A-Z][a-z]+\s+(?:were|are|observed|noticed|had)\b"
    r"|\b[A-Z][a-z]+\s+(?:claims?|argues|counter\s+argues|observed|noticed|says|said)\b",
)
_ASKS = re.compile(
    r"\?|\b(?:explain|justify|predict|suggest|identify|discuss|calculate|find|determine"
    r"|estimate|verify|obtain|express|state|give\s+reasons?|provide"
    r"|what\s+do\s+you\s+think)\b",
    re.IGNORECASE,
)
# A quantity a word problem gives: "24 m/s", "50 g", "6 s", "70%".
_QUANTITY = re.compile(
    r"\d(?:[\d,]*\d)?(?:\.\d+)?\s*(?:%|°\s*[CF]\b|(?:km|cm|mm|m|kg|g|mg|s|min|h|N|J|kJ|W|kW"
    r"|Hz|kHz|K|Pa|L|mL|u|mol|V|A|Ω)(?:\s*(?:/|per)\s*(?:s²|s\^?2|s|h|m³|m\^?3|L|mol))?\b)"
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
SCHOOL_QUESTION_NOTE = (
    "This message is a school exercise. Answer it as the textbook expects, for the "
    "student who asked, at the level the question is written, from what the textbook "
    "teaches (no web search for it): open with the answer itself in plain words, using "
    "the textbook's terms, then a short reason or two to four everyday examples. "
    + WORK_FIRST
    + " Stay at "
    "that level: no university detail, history or regional trivia it did not ask for, and "
    "no side claim you are unsure of. Take the question as written: never call it a trick "
    "or a riddle, never dispute its wording, its options or the textbook, and never ask "
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
    "examples. " + WORK_FIRST + " Take the question as written: never open by disputing "
    "it, correcting its wording or calling it a trick, and keep to what it asks: no "
    "specialist detail or side claims you are unsure of. End when the answer is complete, "
    "with no offer of more."
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
        asked
        and len(stem.split()) >= 3
        and _OWN.search(stem) is None
        and _ALL_ITEMS.search(stem) is None
        and _TASTE.search(stem) is None
        and _CURRENT.search(text) is None
        and _CODE_TALK.search(text) is None
    )


def _anyones(text: str) -> bool:
    """About the asker, code, anything current or a matter of taste."""
    return any(pattern.search(text) is not None for pattern in (_OWN, _CODE_TALK, _CURRENT, _TASTE))


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
    if _choice(text) or _CODE.search(text) or _closing_order(text) or _TEXTBOOK.search(text):
        return True
    if _CODE_TALK.search(text) or _CURRENT.search(text) or _TASTE.search(text):
        return False
    if _ASSERTION.search(text) or _BLANK.search(text) or _OPENING.search(text):
        return True
    if _OWN.search(text):
        return False
    if _ASKS.search(text) is None:
        return False
    return bool(labelled_parts(text) or _SCENARIO.search(text) or len(_QUANTITY.findall(text)) >= 2)


# A question, or an order to explain, opening the message or any sentence of it.
_QUESTION = re.compile(
    r"\?|(?:^|[.!:]\s+)(?:why|how|what|which|who|whom|whose|where|when|is|are|was|were|does"
    r"|do|did|can|could|will|explain|describe|define|state|name|list|compare|discuss"
    r"|identify|justify|suggest|predict|find|calculate|determine)\b",
    re.IGNORECASE,
)
# A task to do, not a question to answer: "Write a poem about rain", "Translate …",
# "Find remote backend jobs", "do a search".
_TASK = re.compile(
    r"^\s*(?:write|draft|make|create|generate|plan|translate|summari[sz]e|rewrite|edit|fix"
    r"|help|remind|search|look\s+up|do\s+a|find\s+(?!the\b)|tell\s+me\s+a\s+(?:joke|story))\b",
    re.IGNORECASE,
)
# Talk with the assistant, or the clock and calendar: "how are you?", "what can you do",
# "what time is it", "What did we decide last time?".
_CHAT = re.compile(
    r"\b(?:how\s+are\s+you|who\s+are\s+you|are\s+you|can\s+you\s+(?:do|help|see|hear)"
    r"|what\s+can\s+you|what\s+time|what\s+day|today'?s\s+date|we|our|us)\b",
    re.IGNORECASE,
)


def is_factual_question(query: str) -> bool:
    """A question about the world, not about the asker, code, anything current or taste."""
    text = query.strip()
    return (
        3 <= len(text.split()) <= 150
        and _QUESTION.search(text) is not None
        and _TASK.search(text) is None
        and _CHAT.search(text) is None
        and not _anyones(text)
        and not is_social_opener(text)
        and not has_code_syntax(text)
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
    r"|\bcritically\s+examine\b|\bwhat\s+do\s+you\s+think\s+about\s+this\s+statement\b",
    re.IGNORECASE,
)


def needs_reasoned_choice(query: str) -> bool:
    """A school exercise whose answer is a choice or a verdict to reason out first."""
    text = query.strip()
    if not is_school_exercise(text):
        return False
    return bool(_choice(text) or _ASSERTION.search(text) or _VERDICT.search(text))


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
