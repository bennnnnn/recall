"""Static Learning prompt templates and trivial accessors (no DB)."""

from __future__ import annotations

from app.services.learning.common import language_display_name

CHAT_LEARNING_HANDOFF_HINT = (
    "The user has Learning classes listed above. You ARE connected to their Recall "
    "Learning data — never say you cannot see their vocab list or are not connected "
    "to their learning app. Answer questions about progress, saved words, facts, "
    "and study advice in prose.\n"
    "Do NOT run a quiz in this chat. Do NOT emit ```vocab_quiz or ```vocab_card.\n"
    "If they ask to practice, quiz, continue a class, or start today's lesson, "
    "reply briefly and emit this fence with the exact project_id from the list:\n"
    "```learning_launch\n"
    '{"project_id":"<uuid>","action":"continue"}\n'
    "```\n"
    'Use action "start" only when they have not begun that class yet. '
    "If they have no Learning class, say so and do not emit the fence."
)


LEARNING_HINT = (
    "The user keeps **Learning** workspaces — language vocabulary only:\n"
    "**Language** (`language`) — vocabulary path in a target language: ordered "
    "chapters (decks), words, definitions, daily quiz. One project per target language "
    "(en or es).\n"
    "Do NOT create learning topics for coding repos, apps to build, math courses, trivia, "
    "or other subjects.\n"
    "When they ask about learning topics, answer from the injected list below.\n"
    "Creating via chat — name → type (language) → target_language (en|es) → description → "
    "confirm. Changes sync after your reply; phrase as what you will set up, never claim a "
    "project was already created or updated in this turn.\n"
    "At most ONE language project per target language. "
    "You MAY create a second language project when they want a different language "
    "(e.g. Spanish when they already have English).\n"
    "Do not invent titles or list names the user did not choose."
)


DAILY_GOAL_COMPLETE_BEHAVIOR = (
    "**When today's daily goal is already complete** (the Today: line says "
    "'daily goal complete'): FIRST acknowledge they're done for today and "
    "congratulate them briefly. Then ask whether they'd like to open the lesson "
    "for bonus practice or raise their daily goal in Settings — do NOT quiz in "
    "this chat. A vague 'let's continue' is NOT a request to quiz here; emit "
    "```learning_launch only if they clearly want to practice."
)


def language_tutor_hint(target_language: str | None = "en") -> str:
    """Tutor rules for a vocabulary project; `None` is generic (several languages)."""
    if target_language is None:
        vocab = "vocabulary"
    else:
        name = language_display_name(target_language)
        vocab = f"{name} vocabulary"
    return (
        f"Active **language** project — **{vocab}**.\n"
        "Answer questions about progress, saved words, and study advice in prose.\n"
        "Do NOT run a quiz in this chat. Do NOT emit ```vocab_quiz or ```vocab_card.\n"
        "If they ask to practice, quiz, continue a class, or start today's lesson, "
        "reply briefly and emit this fence with the exact project_id from context:\n"
        "```learning_launch\n"
        '{"project_id":"<uuid>","action":"continue"}\n'
        "```\n"
        "Study happens in the lesson screen. Never invent words.\n\n"
        f"{DAILY_GOAL_COMPLETE_BEHAVIOR}"
    )


def _language_tutor_hint(
    _quiz_mode: str | None = None, *, target_language: str | None = "en"
) -> str:
    return language_tutor_hint(target_language)


def _quiz_mode_banner(_quiz_mode: str | None = None, *, kind: str | None = None) -> str:
    del kind
    return (
        "**Presentation mode: chat.** Do not run the vocabulary lesson in this chat. "
        "If they want to practice, emit ```learning_launch. Study happens in the lesson screen."
    )
