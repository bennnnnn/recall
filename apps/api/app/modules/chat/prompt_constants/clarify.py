"""Asking the user with a tap card instead of a paragraph of questions (docs/clarify.md).

``CLARIFY_CARD_HINT`` is the one asking rule: when to ask first, when to answer and offer
a card to tailor, when never, and the ```clarify card's shape. The server checks the
card the model writes (``chat/clarify_card.py``) and reads the user's picks on the next
turn (``chat/clarify_turn.py``).
"""

CLARIFY_CARD_HINT = (
    "Asking the user: when the answer depends on something only they know (their level, "
    "goal, budget, situation) and neither memory nor this chat says it, the tap card is the "
    "only way to ask: never write those questions as prose, a list, or choices in "
    "parentheses. Ask first (one short sentence, then the card, no "
    "answer yet) only when any answer would be a guess, as in 'plan my week' or 'which "
    "laptop should I buy'. When a good general answer exists, give it, and add the card "
    "after it only when their picks would change the answer in a real way. Never for a "
    "plain fact, a sum or a maths, physics or chemistry problem, a greeting, a reminder, a "
    "picture, or a draft whose purpose they gave. One card per reply, at its end: a "
    "```clarify fence holding one JSON object, for example "
    '{"when": "first", "questions": [{"id": "level", "label": "Studied it before", '
    '"question": "Have you studied integrals before?", "options": ["No, never", "A little", '
    '"Yes, I\'m revising"], "multi": false}]}. "when" is "first" (no answer yet) or '
    '"after" (under an answer). 1 to 3 questions, 2 to 4 short options each, all in the '
    'user\'s language; "label" is 2 to 4 words naming the question; "multi" is true only '
    "when several picks make sense. Never add Other, Submit or Skip: the app adds them. A "
    "question with no fixed choices (an email's purpose, their own numbers) is one short "
    "question in prose instead of a card."
)

# The turn after a card. The phone sends the picks as one "Label: pick" line per question.
CLARIFY_PICKS_FIRST_HINT = (
    "The user's message answers the clarify card your last reply asked: each line is a "
    "question's label and what they picked. Now answer the request they made before the "
    "card, in full, built around these details. Do not ask again and do not list their "
    "picks back to them."
)
CLARIFY_PICKS_AFTER_HINT = (
    "The user's message answers the clarify card under your last answer: each line is a "
    "question's label and what they picked. Answer their request again, fitted to these "
    "details: a complete, clear answer on its own, not a patch on the last one. Do not ask "
    "again."
)
# Skip ("Just answer", in their language) or anything typed instead of tapping.
CLARIFY_UNANSWERED_HINT = (
    "Your last reply asked with a clarify card. If this message answers it in other words "
    "or says to skip or just answer, answer the request from before the card now, with your "
    "best general reading for anything they did not say, and do not ask again. If it is a "
    "new question, answer that."
)
