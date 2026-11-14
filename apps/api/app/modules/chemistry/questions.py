"""The questions a chemistry message asks, each as a reader takes it.

Its labelled parts, each with the statement before the first label, or else its question
sentences that ask chemistry, each with the statements before it. A question that names no
substance takes the one the message named before it: "(b) How many moles are in 34 g of it?" is
asked of the NH3 of part (a). ``parts`` answers them one by one; ``direct`` never lets an
instant reply answer fewer of them than the message asks.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.modules.chemistry.request import is_chemistry_question
from app.modules.chemistry.species_facts import named_species
from app.services.question_parts import labelled_part_texts, labelled_parts

# A sentence ends at "?" or "!", or at a full stop before a capital ("… 0.010 M HCl. What …");
# a decimal point ("0.010") ends nothing.
_SENTENCE_END = re.compile(r"(?<=[?!])\s+|(?<=[A-Za-z0-9)\]%]\.)\s+(?=[A-Z])")


def _question_sentences(text: str) -> list[tuple[str, str]]:
    """Each sentence that asks something, with the statements before it."""
    statements: list[str] = []
    asked: list[tuple[str, str]] = []
    for sentence in (piece.strip() for piece in _SENTENCE_END.split(text)):
        if sentence.endswith("?"):
            asked.append((" ".join(statements), sentence))
        elif sentence:
            statements.append(sentence)
    return asked


@dataclass(frozen=True)
class Question:
    """One question of the message: as asked (its setup before it), and as a reader takes it,
    with the substance the message named before it when it names none itself."""

    asked: str
    read: str


def _with_substance(asked: Iterable[tuple[str, str]]) -> list[Question]:
    questions: list[Question] = []
    said = ""
    for setup, question in asked:
        own = f"{setup} {question}".strip()
        before = named_species(f"{setup} {said}")
        carried = not named_species(own) and len(before) == 1
        read = f"{setup} For {before[0]}: {question}".strip() if carried else own
        questions.append(Question(own, read))
        said = f"{said} {question}"
    return questions


def chemistry_questions(text: str) -> tuple[Question, ...]:
    """The questions ``text`` asks: every labelled part, or every question sentence that
    asks chemistry."""
    setup, labelled = labelled_part_texts(text)
    if labelled:
        return tuple(_with_substance((setup, part) for part in labelled))
    questions = _with_substance(_question_sentences(text))
    return tuple(question for question in questions if is_chemistry_question(question.read))


def asks_several(text: str) -> bool:
    """A cheap look first: two labels, or two question marks."""
    return labelled_parts(text) >= 2 or text.count("?") >= 2


def asks_more_questions(text: str, answers: str) -> bool:
    """``text`` asks more chemistry questions than ``answers`` has lines."""
    if not asks_several(text):
        return False
    lines = [line for line in answers.splitlines() if line.strip()]
    return len(chemistry_questions(text)) > max(len(lines), 1)
