"""A verified card only from a question the readers read whole (2026-11-01 baseline).

The subject readers are English grammars that read numbers the English way. "Deux
résistances de 10 ohms sont en parallèle sous 5 V, courant total ?" got a checked 0.5 A for
one resistor ("deux" unread; two in parallel draw 1 A), and "1.200 + 800" from a Spanish user
a checked 801.2 (1.200 is 1200 there). A question in another language, or with a number its
writer's locale reads otherwise, keeps no verified result: no card, no picture, no instant
reply. An English question keeps its card, names and symbols included.
"""

from __future__ import annotations

import pytest

from app.modules.chat.prompt_builder import SubjectFetch
from app.modules.chat.tool_verified import with_tool_verified
from app.modules.chat.whole_question import answers_with, whole_question_fetch
from app.modules.turn_reading.readable import misread_number, other_language, unreadable
from app.services.solving import VerifiedSolveBlock

_DROPPED = SubjectFetch(None, None, False, None, None)


@pytest.mark.parametrize(
    "question",
    [
        "Deux résistances de 10 ohms sont en parallèle sous 5 V, courant total ?",
        "Dos resistencias de 10 ohmios están en paralelo a 5 V, ¿cuál es la corriente total?",
        "Berechne die Geschwindigkeit eines Autos, das in 5 s 100 m fährt.",
        "Calcola la velocità di un'auto che percorre 100 m in 5 s.",
        "Calcule a velocidade de um carro que percorre 100 m em 5 s.",
        "5 saniyede 100 m giden bir arabanın hızı nedir?",
        "2 A ን በ15 Ω ተከላካይ ውስጥ ለማስገደድ ምን ያህል ቮልቴጅ ያስፈልጋል?",
        "Какое напряжение нужно, чтобы через резистор 15 Ω шёл ток 2 A?",
        "pOH 3.2 है, pH ज्ञात कीजिए।",
        # One word of another language and none of English.
        "résous 3x + 7 = 22",
        "resuelve 2x + 3 = 7",
        "si x = 2, halla 3x + 1",
    ],
)
def test_a_question_in_another_language_is_read_as_one(question: str) -> None:
    assert other_language(question)
    assert unreadable(question, "en") == "other_language"


@pytest.mark.parametrize(
    "question",
    [
        "What is the de Broglie wavelength of an electron moving at 2 x 10^6 m/s?",
        "de Broglie wavelength of a 145 g baseball thrown at 40 m/s",
        "explain le chatelier's principle",
        "Use the van der Waals equation for 1 mol of CO2 at 300 K in 0.5 L",
        "Use L'Hôpital's rule to find the limit of sin(x)/x as x approaches 0",
        "José pushes a 20 kg box with a net force of 50 N. what is its acceleration?",
        "a 5 µF capacitor is charged to 12 V. how much energy does it store?",
        "Light enters glass at θ = 30°; n = 1.5. Find the angle of refraction.",
        "angles of 30º and 60º in a triangle, find the third",
        "Secants CA and CE intersect a circle at A, B, D and E. DA bisects ∠CAB.",
        "the meeting is at 3pm EST, what time is that in addis?",
        "What is the atomic number of La, Es and Os?",
        "I've got 2x + 3 = 7, can you solve it?",
        "solve log2(x) + log2(x-2) = 3",
        "The mean of six numbers is 12. Find the sixth number.",
        # No words: no language.
        "1.200 + 800",
        "x+y+z=6, 2x-y+z=3, x+2y-z=2",
        "$\\int_{0}^{2} x^3\\,dx$",
    ],
)
def test_an_english_question_is_not_another_language(question: str) -> None:
    assert not other_language(question)


@pytest.mark.parametrize(
    ("question", "locale", "misread"),
    [
        # A dot groups thousands in Spanish, German, Italian, Portuguese and Turkish.
        ("1.200 + 800", "es", True),
        ("a 1.500 kg car", "de", True),
        ("media de 1.200, 1.500 y 1.800", "es", True),
        ("2.718^2", "it", True),
        ("1.200 + 800", "en", False),
        ("1.200 + 800", "fr", False),
        ("0.125 + 1", "es", False),
        ("3.14159 * 2", "es", False),
        ("2.5 + 1.25", "pt", False),
        # A comma is the decimal mark there and in French and Russian.
        ("1,200 + 800", "fr", True),
        ("1,200 + 800", "ru", True),
        ("1,200 + 800", "en", False),
        ("1,200 + 800", "am", False),
        ("x+y+z=6, 2x-y+z=3", "fr", False),
        # Groups set apart by a space are read as two numbers, whoever writes them.
        ("a car of mass 1 200 kg", "en", True),
        ("12 000 + 800", "en", True),
        ("1 200 + 800", "fr", True),
        ("3 + 4", "en", False),
        ("x^2 + 4 = 100", "en", False),
        ("```\n1 200\n```", "en", False),
    ],
)
def test_a_number_the_writer_reads_otherwise(question: str, locale: str, misread: bool) -> None:
    assert misread_number(question, locale) is misread


def _fetched(answer: str = "0.5\\,\\mathrm{A}", *, direct: str | None = None) -> SubjectFetch:
    verified = VerifiedSolveBlock(text="block", subject="physics", display_answer=answer)
    return SubjectFetch("block", verified, False, None, direct)


def test_a_question_in_another_language_loses_its_verified_result() -> None:
    question = "Deux résistances de 10 ohms sont en parallèle sous 5 V, courant total ?"
    assert whole_question_fetch(question, _fetched()) == _DROPPED


def test_a_number_the_locale_reads_otherwise_loses_its_verified_result() -> None:
    fetched = _fetched("801.2")
    assert whole_question_fetch("1.200 + 800", fetched, locale="es") == _DROPPED
    assert whole_question_fetch("1.200 + 800", fetched, locale="en") == fetched


def test_an_english_question_keeps_its_verified_result() -> None:
    fetched = _fetched("30\\,\\mathrm{V}")
    question = "What voltage drives 2 A through a 15 Ω resistor?"
    assert whole_question_fetch(question, fetched, locale="fr") == fetched


def test_a_picture_without_a_card_goes_too() -> None:
    """The circuit drawn for the French question showed one resistor."""
    picture = VerifiedSolveBlock(text="block", subject="physics")
    question = "Deux résistances de 10 ohms sont en parallèle sous 5 V, courant total ?"
    assert not answers_with(question, picture)
    assert answers_with("Draw two 10 Ω resistors in parallel across 5 V", picture)


def test_a_reply_written_whole_by_the_solvers_goes_too() -> None:
    """A reply both halves of "…, and also …" wrote themselves goes when one is unread."""
    fetched = SubjectFetch(None, None, False, None, "801.2\n\n---\n\nx = 2")
    question = "1.200 + 800, and also solve 2x = 4"
    assert whole_question_fetch(question, fetched, locale="es") == _DROPPED
    assert whole_question_fetch(question, fetched, locale="en") == fetched


def test_a_follow_up_to_an_unread_question_gets_no_card() -> None:
    """The follow-up is English; the problem it solves again is the French line before it."""
    problem = "Deux résistances de 10 ohms sont en parallèle sous 5 V, courant total ?"
    fetched = _fetched()
    assert whole_question_fetch("how?", fetched, problems=(None, None, problem)) == _DROPPED
    assert whole_question_fetch("how?", fetched, problems=(None, None, None)) == fetched


def test_the_tool_loop_gives_an_unread_question_no_card() -> None:
    tool = VerifiedSolveBlock(text="tool", subject="math", canonical_answer="801.2")
    assert with_tool_verified(None, tool, "1.200 + 800", "es") is None
    assert with_tool_verified(None, tool, "1.200 + 800", "en") is tool
