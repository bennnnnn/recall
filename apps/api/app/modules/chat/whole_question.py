"""A verified result answers the question asked, all of it, or is not shown.

A subject reader answers one thing. A question in parts, with several reactions, or with
options to choose from asks more, and the one thing it answered was shown as the checked
answer: "Electrons = 31" for "how many electrons in its valence shell? a 5 b 4 c 3 d 2",
"6" for "belongs to group: a IIIA b IVA c VIA d VIIA", "2 Fe + O₂ → 2 FeO" for the option
that forms iron(II) oxide, "3:2" for a five-part question, and part (a) alone of four pH
calculations (2026-10-30, Ethiopian Grade 7-12 chemistry books). Such a result is dropped
whole (its prompt block, its card and its instant reply), and the model answers the
question; a result that answers every part, or is one of the options, stays.
"""

from __future__ import annotations

import re

from app.modules.chat.prompt_builder import SubjectFetch
from app.services.question_parts import asks_more_parts

# A reaction: "→", "->", "⟶", "=>" between two sides.
_ARROW = re.compile(r"→|⟶|->|=>|⇌")
# A label opening an option or a part: "a 5", "(b) 4", "c) 3", "D Fe + O → FeO". Bare
# letters count only at a line's start or after two spaces, as a book prints options.
_LABEL = re.compile(
    r"(?:(?:^|(?<=\n)|(?<=\s\s))\(?([a-eA-E])(?:[).:]\s*|\s+)"
    r"|(?<=[\s(])\(?([a-eA-E])\)\s*)(?=\S)"
)
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
_MARKUP = re.compile(r"\\[a-zA-Z]+|[{}$*_`\\]")


def labelled_choices(question: str) -> list[str]:
    """The texts of a run of two or more labels in order (a, b, c …), or none."""
    labels = [
        (match.start(), match.end(), (match.group(1) or match.group(2)))
        for match in _LABEL.finditer(question)
    ]
    for first, (_, _, letter) in enumerate(labels):
        if letter.lower() != "a":
            continue
        chain = [labels[first]]
        for later in labels[first + 1 :]:
            if later[2] == chr(ord(chain[-1][2]) + 1):
                chain.append(later)
        if len(chain) >= 2:
            ends = [start for start, _, _ in chain[1:]] + [len(question)]
            return [
                question[end:stop].splitlines()[0].strip() if question[end:stop] else ""
                for (_, end, _), stop in zip(chain, ends, strict=True)
            ]
    return []


# A verdict on a set of solutions, which only an equation or system to solve asks for.
_SOLUTION_VERDICT = re.compile(
    r"no\s+solutions?|infinitely\s+many|all\s+real\s+numbers|free\s+variable", re.IGNORECASE
)
_ASKS_TO_SOLVE = re.compile(
    r"\bsolve|\bsolutions?\b|\bconsistent\b|\bsatisf|\bfor\s+which\s+values?|\broots?\b",
    re.IGNORECASE,
)
# A size that is never negative: "the length of the radius", "how long", "how many".
_MAGNITUDE_ASK = re.compile(
    r"\b(?:length|radius|diameter|side|height|width|depth|distance|perimeter|area|volume"
    r"|mass|speed|age|number\s+of)\b|\bhow\s+(?:long|far|many|much|tall|wide|high|old)\b",
    re.IGNORECASE,
)
_SIGNED = re.compile(r"\\pm|±|(?:^|[=(,\s])-\s*\d")


# A proof has no value to certify: "Prove by induction …" showed "n = 0, 1/2, 1".
_ASKS_A_PROOF = re.compile(
    r"\b(?:prove|show\s+that|verify\s+that|demonstrate\s+that|by\s+induction)\b", re.IGNORECASE
)
# A value at a point: "the gradient at x = 3" is a number, not f'(x).
_AT_A_POINT = re.compile(
    r"\b(?:at|when|where)\s+(?:the\s+point\s+)?(?:[a-z]\s*=\s*-?\d|\(\s*-?\d)", re.IGNORECASE
)
_FREE_VARIABLE = re.compile(r"(?<![a-zA-Z\\])[a-z](?![a-zA-Z])")
_ASKS_AN_EQUATION = re.compile(r"\bequation\s+of\b", re.IGNORECASE)
# Solutions of a kind: "the rational zeros", "integer solutions".
_QUALIFIED_SOLUTIONS = re.compile(
    r"\b(?:rational|integer|whole[- ]number|natural[- ]number|positive)\s+"
    r"(?:zeros?|roots?|solutions?|values?|numbers?)",
    re.IGNORECASE,
)
_NOT_RATIONAL = re.compile(r"\d\.\d{3,}|\\sqrt|(?<![a-zA-Z\\])i(?![a-zA-Z])")


def answers_the_question(question: str, answer: str) -> bool:
    """``answer`` answers what ``question`` asks, all of it, and says something new: a
    whole question, not a restatement of it, a verdict only on an equation to solve, a size
    never signed, no value for a proof, a value at a point with no variable left, an
    equation where one is asked, and solutions of the kind asked."""
    return (
        answers_whole_question(question, answer)
        and not _restates(question, answer)
        and not (_SOLUTION_VERDICT.search(answer) and not _ASKS_TO_SOLVE.search(question))
        and not (_MAGNITUDE_ASK.search(question) and _SIGNED.search(answer))
        and not _ASKS_A_PROOF.search(question)
        and not (_AT_A_POINT.search(question) and _FREE_VARIABLE.search(_right_side(answer)))
        and not (_ASKS_AN_EQUATION.search(question) and "=" not in answer)
        and not (_QUALIFIED_SOLUTIONS.search(question) and _NOT_RATIONAL.search(answer))
    )


def _right_side(answer: str) -> str:
    """What the answer gives: after its last "=", without LaTeX commands or units."""
    value = answer.rsplit("=", 1)[-1]
    return re.sub(r"\\[a-zA-Z]+(?:\{[^{}]*\})?|\{|\}", " ", value)


def _restates(question: str, answer: str) -> bool:
    """A piece of ``answer`` is a piece of ``question`` as written: "the cube root of
    27a^3 + 54a^2b + …" certified the expression itself, and "a x b if a = 3i - 2j + 5k"
    the givens."""
    asked = _squashed(question)
    pieces = [_squashed(piece) for piece in re.split(r",|\\quad|\n", answer)]
    return any(len(piece) >= 4 and piece in asked for piece in pieces)


def _squashed(text: str) -> str:
    """Letters, digits and signs only: "27 a^{3} + 54 a^{2} b" and "27a^3 + 54a^2b" alike."""
    plain = re.sub(r"\\(?:text|mathrm|left|right)\b|\\[a-zA-Z]+", " ", text)
    plain = plain.replace(chr(0x2013), "-").replace(chr(0x2212), "-")
    return re.sub(r"[^0-9a-zA-Z+\-=*/]", "", plain).lower()


def answers_whole_question(question: str, answer: str) -> bool:
    """``answer`` is all ``question`` asks: no second reaction, every part answered, and
    one of its options when it gives some."""
    if len(_ARROW.findall(question)) >= 2:
        return False
    choices = labelled_choices(question)
    if not choices:
        return not asks_more_parts(question, answer)
    if _are_options(choices):
        return any(_same_choice(answer, choice) for choice in choices)
    # Parts: one line of the answer for each.
    return len([line for line in answer.splitlines() if line.strip()]) >= len(choices)


def _are_options(choices: list[str]) -> bool:
    """Short labelled answers to pick from, not parts that each ask something."""
    return len(choices) >= 3 and all(len(c.split()) <= 8 and "?" not in c for c in choices)


def _same_choice(answer: str, choice: str) -> bool:
    """The answer states this option: its number, or its words. An equation is no number."""
    plain_answer = _MARKUP.sub("", answer).lower()
    plain_choice = _MARKUP.sub("", choice).lower().strip()
    if not plain_choice:
        return False
    if _NUMBER.fullmatch(plain_choice.split()[0]):
        if _ARROW.search(plain_answer):
            return False
        answered = _NUMBER.findall(plain_answer.split("=")[-1])
        return bool(answered) and float(answered[-1]) == float(plain_choice.split()[0])
    return plain_choice in plain_answer


def whole_question_fetch(question: str, fetched: SubjectFetch) -> SubjectFetch:
    """``fetched`` as it was, or without its verified result when that answers part of
    ``question``."""
    verified = fetched.verified
    if verified is None or fetched.direct_text is not None:
        return fetched
    answer = verified.display_answer or verified.canonical_answer or ""
    if not answer or answers_the_question(question, answer):
        return fetched
    return SubjectFetch(
        subject_block=None,
        verified=None,
        solver_unverified=False,
        unverified_subject=None,
        direct_text=None,
    )
