"""Learning, quiz, and vocabulary prompt hints."""

from app.services.projects.prompts import VOCAB_LEARNING_FORMATS_BLOCK

DAY_LEARNING_SNAPSHOT_HINT = (
    "When 'Today's learning progress' is in context, those lines are authoritative for the "
    "user's local calendar day. Never reuse yesterday's scores from memory or chat history.\n"
    "Only mention tracks that appear in that block (vocabulary quiz) — never invent another "
    "kind of class if it is not listed.\n"
    "If today's learning progress lists an incomplete goal, mention it briefly. "
    "If it says there is **no active learning class**, do not mention quizzes at all. "
    "If a listed goal is complete, you may note that track only — do not invent incomplete "
    "progress or extra classes."
)

QUIZ_ANSWER_HINT = (
    "The user just answered a multiple-choice quiz with A, B, C, or D. "
    "The previous assistant message has the question, choices, and correct letter. "
    "If an **Automated grading** line is present, it is authoritative — match it exactly.\n"
    "Structure your reply as:\n"
    "1) **Brief feedback only** (1-2 sentences):\n"
    "   - CORRECT: congratulate the answer (letter + choice text), not a topic label "
    '(e.g. say "apple" — never "Food is correct").\n'
    "   - WRONG: say they were wrong. Give a short hint (clue) — do NOT reveal the correct "
    "letter or full answer yet. Never say 'word mastered' or congratulate. "
    "Do NOT use spoiler syntax (>! !<).\n"
    "2) **Next step:**\n"
    "   - CORRECT: continue with a DIFFERENT next word using a **different** "
    "learning format when possible (teach→use with vocab_card, use→define open-ended, or "
    "occasional MCQ ```vocab_quiz) — never default to MCQ every turn.\n"
    "   - WRONG (tries 1-2): stop after the hint. Do NOT redisplay the question, choices, or a "
    "```vocab_quiz fence. The previous chips stay available — they will answer again.\n"
    "   - FAILED (3rd wrong try): briefly reveal the correct answer, keep as learning for "
    "next time (not mastered), then continue with a DIFFERENT next word.\n"
    "Stay on vocabulary. Never invent words. Never emit a trivia or general-knowledge quiz.\n"
    "Vocabulary format rotation:\n"
    f"{VOCAB_LEARNING_FORMATS_BLOCK}\n"
    "Never use plain Q:/A: lines or multiple questions in one message.\n"
    "Mastering is recorded automatically on correct MCQ answers — do not sync master on a wrong answer."
)

VOCAB_CHAT_ANSWER_HINT = (
    "The user is answering your vocabulary prompt from the previous assistant message "
    "(sentence, definition, or MCQ). Grade their reply **strictly**:\n"
    "- Only say correct if their answer actually demonstrates understanding of the word "
    "(good sentence uses the word correctly; definition matches the meaning).\n"
    "- Gibberish, unrelated text, random single letters (unless you asked for A-D), or "
    "placeholder replies = **wrong** — never congratulate those.\n"
    "- If wrong (tries 1-2): say wrong and give a short hint (not the full answer). Do NOT "
    "redisplay an MCQ fence. Never say 'word mastered'.\n"
    "- If failed after repeated weak tries: briefly reveal the answer, keep as learning, "
    "then continue with a DIFFERENT next word in another learning format.\n"
    "- If correct: congratulate briefly, then continue with a DIFFERENT next word — prefer a "
    "**different** format than the one you just used (teach→use, use→define, occasional MCQ).\n"
    f"{VOCAB_LEARNING_FORMATS_BLOCK}\n"
    "- Only treat as mastered when genuinely correct (MCQ auto-grades; for open-ended, "
    "confirm clearly so project sync can record mastery).\n"
    "- When the answer is wrong / weak and you move on (or they clearly failed): the app "
    "records the fail via project sync — say they got it wrong and keep the word as learning; "
    "do not call it 'missed' (that means skipped a study day)."
)


def format_quiz_grading_hint(
    *,
    is_correct: bool,
    user_letter: str,
    correct_letter: str,
    word: str,
    quiz_type: str | None = None,
    question: str | None = None,
    attempt: int = 1,
    tries_exhausted: bool = False,
) -> str:
    from app.services.vocab_quiz import MAX_QUIZ_TRIES_PER_QUESTION

    # quiz_type / question remain on the fence parser; Learning is vocabulary only.
    _ = (quiz_type, question)
    if is_correct:
        follow_up = (
            f'Congratulate briefly that "{word}" is correct. '
            f'Do NOT re-ask "{word}". '
            "Then continue with a DIFFERENT next word using a different learning format "
            "(teach→use, use→define, or occasional MCQ) — do not default to MCQ every turn."
        )
        verdict = "CORRECT"
    elif tries_exhausted:
        follow_up = (
            f'They failed "{word}" after {attempt} tries. Briefly reveal the correct answer '
            f"({correct_letter}). Keep it as learning/failed for next time — do NOT say "
            f'mastered. Then continue with a DIFFERENT next word (not "{word}") using another '
            "learning format (teach→use, use→define, or MCQ)."
        )
        verdict = "FAILED"
    else:
        follow_up = (
            f'Tell them "{word}" was wrong (try {attempt}/{MAX_QUIZ_TRIES_PER_QUESTION}, '
            f"they picked {user_letter}). "
            "Give a short hint only — do NOT reveal the correct letter or full definition. "
            "Do NOT redisplay the question, choices, or a ```vocab_quiz fence. "
            "They will tap an answer on the previous question. "
            "Do NOT say 'word mastered'."
        )
        verdict = "WRONG"
    subject = f'"{word}"'
    # For WRONG non-exhausted attempts (tries 1-2), omit the correct letter from
    # the authoritative block — the follow-up already says "do NOT reveal," but
    # including the letter in the same system prompt leaks it to the model.
    # (LANG-PROMPT-001)
    if verdict == "WRONG" and not tries_exhausted:
        return (
            f"**Automated grading (authoritative — your feedback MUST match this):** "
            f"For {subject}, user answered {user_letter}. "
            f"Result: {verdict}. {follow_up}"
        )
    return (
        f"**Automated grading (authoritative — your feedback MUST match this):** "
        f"For {subject}, user answered {user_letter}. Correct answer: {correct_letter}. "
        f"Result: {verdict}. {follow_up}"
    )


QUIZ_RECENT_MESSAGE_LIMIT = 12
