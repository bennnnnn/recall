"""Quiz me, flashcards, true/false: practice the phone draws as ```quiz cards.

A lesson's "Your turn" already uses the card; an explicit request for practice gets
one card per question, so the answers stay hidden until the user checks them. A message the
turn's read calls an answer to the last reply's card is graded against that card's answer.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.chat.quiz_cards import PracticeCard

QUIZ_FORMAT_HINT = (
    "This turn asked for a quiz, flashcards or true/false questions. Each question is its "
    "own ```quiz card the app lets them answer and check: ```quiz alone on its line, the "
    "JSON on the next, then the closing fence. Never write an answer in the text; the "
    "card holds it.\n"
    '- Multiple choice: {"label": "Question 1", "question": "...", "options": ["...", '
    '"...", "...", "..."], "answer": <0-based index of the right option>, "explanation": '
    '"<why, in one or two sentences>"}; make the wrong options real mistakes.\n'
    '- True/false: the same with "options": ["True", "False"].\n'
    '- Flashcard: {"label": "Card 1", "question": "<the front>", "explanation": "<the '
    'back>"} with no options; the app shows the back when they tap Show answer.\n'
    "Each asks only what the chat has taught or the user asked about, never a question this "
    "chat already asked. Exactly one option is right: check that each wrong option is false "
    "for the question as written. "
    "As many as they asked for (five when they named no number, at most ten). One short "
    "line before the first card and one line after the last offering another round. No "
    "headings, no numbered list, no answer key."
)


def quiz_answer_note(cards: Sequence[PracticeCard]) -> str:
    """Beside a message the read calls an answer to the last reply, which ended on cards:
    an answer to them is graded against them; "ok next", which the read calls an answer too,
    goes on.

    "1.2 times 10 to the 24?" answered a lesson's card on the molecules in 2 mol of water; the
    turn laid it out as a calculation, Given to Answer, and then asked whether it was "asking
    how that compares to the answer on the card" (the owner's chat, 2026-11-14)."""
    keys = "; ".join(
        f'{card.label or card.question[:60]}: "{card.right}"' for card in cards if card.right
    )
    return (
        f"The practice card in your last reply has the right answer {keys}. When this message "
        "gives an answer to it, grade it against that answer in a sentence or two, the way a "
        "tutor does: a rounded or reworded answer that means the same is right. No Given, "
        "Required or worked layout and no answer card; show the working only to fix a wrong "
        "answer. A message that only says to go on ('next', 'ok') is no answer: no grade and "
        "no word about the card. Either way, then go on as the conversation does."
    )


# Beside a message whose reply may set practice (``practice_asked``); the finalize pass reads
# the questions back by this opening.
PRACTICE_ASKED_OPENING = "Practice questions this chat has already asked"


def practice_asked_notes(questions: Sequence[str]) -> list[str]:
    """The chat's earlier practice questions, one a line, when there are any: a new card
    asks something else."""
    if not questions:
        return []
    listed = "\n".join(f"- {question}" for question in questions)
    return [
        f"{PRACTICE_ASKED_OPENING}; any new practice card asks something else, never one of "
        "these again, reworded or with the same example and numbers:\n" + listed
    ]
