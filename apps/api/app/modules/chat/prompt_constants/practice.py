"""Quiz me, flashcards, true/false: practice the phone draws as ```quiz cards.

A lesson's "Your turn" already uses the card; an explicit request for practice gets
one card per question, so the answers stay hidden until the user checks them.
"""

import re

_PRACTICE_NOUN = (
    r"(?:quiz(?:zes)?|flash\s?cards?|true[\s/-]+(?:or[\s-]+)?false|multiple[\s-]+choice|mcqs?)"
)
# "Give me a quick geography quiz": the quiz is what they asked for. "Give me tips for
# my quiz" and "make sure I pass my quiz" name one they already have.
_PRACTICE_ASK = re.compile(
    r"(?:"
    r"\b(?:quiz|test)\s+me\b|"
    r"\b(?:make|give|create|write|generate|build|prepare|do|run)\s+(?:(?:me|us)\s+)?"
    r"(?:(?:a|an|the|some|another|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"\d+[\s-]questions?|\d+|few|quick|short|pop|small|little|fun|simple|hard|easy|tricky|"
    r"practice|review|new|more)\s+){0,3}"
    r"(?:(?!(?:my|our|your|his|her|their|for|to|about|on|of|in|with|sure|i|me)\b)"
    r"[a-z]+\s+){0,2}" + _PRACTICE_NOUN + r"\b|"
    r"^\s*(?:some\s+)?flash\s?cards?\s+(?:on|about|for)\b|"
    r"\btrue[\s/-]+(?:or[\s-]+)?false\s+questions?\b|"
    r"\bmultiple[\s-]+choice\s+questions?\b"
    r")",
    re.IGNORECASE,
)
# Asked how, asked for the answers in the text (a teacher's answer key), or asked to
# build something that runs quizzes ("a quiz app in React").
_NOT_CARDS = re.compile(
    r"\bhow\s+(?:to|(?:do|can|should)\s+(?:i|you|we))\b|"
    r"\banswer\s+key\b|"
    r"\bwith\s+(?:the\s+)?(?:answers|solutions)\b|"
    r"\b(?:quiz(?:zes)?|flash\s?cards?|trivia)\s+(?:app|apps|game|site|website|page|"
    r"component|form|bot|feature|night|show|maker|generator)\b",
    re.IGNORECASE,
)

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
    "As many as they asked for (five when they named no number, at most ten). One short "
    "line before the first card and one line after the last offering another round. No "
    "headings, no numbered list, no answer key."
)


def is_practice_request(text: str) -> bool:
    """True for "quiz me on X", "make flashcards for Y", "5 true/false questions about Z"."""
    cleaned = text.strip()
    if not cleaned or len(cleaned) > 400:
        return False
    return _PRACTICE_ASK.search(cleaned) is not None and _NOT_CARDS.search(cleaned) is None
