"""Quiz me, flashcards, true/false: practice the phone draws as ```quiz cards.

A lesson's "Your turn" already uses the card; an explicit request for practice gets
one card per question, so the answers stay hidden until the user checks them. A message the
turn's read calls an answer to the last reply's card is graded against that card's answer.
"""

from __future__ import annotations

from collections.abc import Sequence

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


def quiz_verdict_note(verdicts: Sequence[str]) -> str:
    """Beside a message that answers the last reply's cards: the server's verdict on each.

    "1.2 times 10 to the 24?" answered a lesson's card on the molecules in 2 mol of water; the
    turn laid it out as a calculation, Given to Answer, and then asked whether it was "asking
    how that compares to the answer on the card"; told only the right answer's words, the
    reply graded "b" for B wrong and "a" right (the owner's chat, 2026-11-14)."""
    listed = "\n".join(f"- {verdict}" for verdict in verdicts)
    return (
        "The app checked this message against the practice card in your last reply:\n"
        f"{listed}\n"
        'Open with that verdict in a sentence or two, the way a tutor does ("Correct! 🎉", or '
        '"Not quite" and the one fix), naming their option by its letter and words. No Given, '
        "Required or worked layout and no answer card. Then go on as the conversation does."
    )


# Beside a message whose reply may set practice (``practice_asked``); the finalize pass reads
# the questions back by this opening.
PRACTICE_ASKED_OPENING = "Practice cards this chat has already shown"


def practice_asked_notes(cards: Sequence[str]) -> list[str]:
    """The chat's earlier practice cards, one a line (question, code, options), when there
    are any: a new card asks something else."""
    if not cards:
        return []
    listed = "\n".join(f"- {card}" for card in cards)
    return [
        f"{PRACTICE_ASKED_OPENING}; a new card asks something else: never one of these again, "
        "nor its example and numbers reworded. A question's words may repeat with a new "
        'example ("What will this code print?" over new code):\n' + listed
    ]
