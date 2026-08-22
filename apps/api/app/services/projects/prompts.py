"""Static Learning prompt templates and trivial accessors (no DB)."""

from __future__ import annotations

from app.models.orm import Project
from app.models.schemas import ProjectStats
from app.services.projects.common import language_display_name

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


PROJECT_HINT = (
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
    "(e.g. Spanish when they already have English). Use set_level on the existing project "
    "when skill in that language grows.\n"
    "When telling the user their level, use the plain label only (Beginner, Elementary, "
    "Intermediate, …) — do not mention CEFR or A1–C2 codes unless they ask.\n"
    "Do not invent titles or list names the user did not choose."
)


LEVEL_GUIDANCE: dict[str, str] = {
    "level1": (
        "Beginner: only basic high-frequency words — cat, eat, book, go, hello, water. "
        "Never quiz or add advanced/rare words (ubiquitous, pragmatic, ephemeral, mitigate)."
    ),
    "level2": (
        "Elementary: everyday words a new learner meets in simple conversations. "
        "Avoid academic or rare vocabulary."
    ),
    "level3": (
        "Intermediate: common words plus some idioms. Still avoid highly specialized jargon."
    ),
    "level4": (
        "Upper intermediate: broader vocabulary including less common but still useful words."
    ),
    "level5": ("Advanced: sophisticated vocabulary including nuance and formal register."),
    "level6": ("Fluent: full range including rare, literary, and technical words when relevant."),
}


VOCAB_QUIZ_FENCE_EXAMPLE = (
    "```vocab_quiz\n"
    '{"word":"apple","question":"What does it mean?",'
    '"correct":"A",'
    '"choices":[{"letter":"A","text":"a red fruit"},{"letter":"B","text":"a vehicle"},'
    '{"letter":"C","text":"a feeling"},{"letter":"D","text":"a color"}]}\n'
    "```"
)


VOCAB_QUIZ_FORMAT_BLOCK = (
    "Emit ONLY the ```vocab_quiz fence below — do NOT also write a markdown Q:/A: block "
    "or repeat the question/choices in plain text. The fence renders as tappable chips.\n"
    f"{VOCAB_QUIZ_FENCE_EXAMPLE}"
)


VOCAB_CARD_FENCE_EXAMPLE = (
    '```vocab_card\n{"word":"serendipity","definition":"finding something good by accident"}\n```'
)


# Learning-oriented rotation for vocabulary.
VOCAB_LEARNING_FORMATS_BLOCK = (
    "Rotate these formats across turns (vary; do **not** default to MCQ every time):\n"
    "1) **Teach → use:** show a ```vocab_card``` with **word + definition only** "
    "(do **NOT** include example_sentence — that spoils the exercise). Then ask the user to "
    "write their **own** sentence using the word. Example card:\n"
    f"{VOCAB_CARD_FENCE_EXAMPLE}\n"
    "Then: *Write your own sentence with **serendipity**.* "
    "Only after they answer may you share an example sentence.\n"
    "2) **Use → define:** give one clear example sentence with the target word in **bold**, "
    "then ask what it means in their own words (open-ended — no A–D). "
    "Do **not** show the definition until after they answer.\n"
    "3) **Quick check (MCQ):** about **one turn in three**, use A–D tap chips:\n"
    f"{VOCAB_QUIZ_FORMAT_BLOCK}\n"
    "One word per turn. Prefer teach→use and use→define for learning; MCQ is a quick check only."
)


DAILY_GOAL_COMPLETE_BEHAVIOR = (
    "**When today's daily goal is already complete** (the Today: line says "
    "'daily goal complete'): FIRST acknowledge they're done for today and "
    "congratulate them briefly. Then ask whether they'd like bonus questions "
    "or to raise their daily goal in Settings — do NOT serve a new question "
    "unless they clearly ask for more (e.g. 'bonus', 'one more', 'keep "
    "going'). A vague 'let's continue' is NOT a request for more questions "
    "when the goal is already met."
)


LANGUAGE_BONUS_QUIZ_RULES = (
    "**Bonus practice (after today's goal):** When the user explicitly asks for more quiz, bonus "
    "words, or extra practice beyond today's goal, continue with the same learning-format "
    f"rotation — one word per turn.\n{VOCAB_LEARNING_FORMATS_BLOCK}"
)


def language_tutor_hint(target_language: str | None = "en") -> str:
    """Tutor rules for a vocabulary project; `None` is generic (several languages)."""
    if target_language is None:
        vocab = "vocabulary"
        skill = "skill level in that language"
    else:
        name = language_display_name(target_language)
        vocab = f"{name} vocabulary"
        skill = f"{name} skill level"
    return (
        f"Active **language** project — **daily {vocab} in chat**.\n"
        f"The project **level** is the user's **{skill}** (level1=beginner … level6=fluent).\n"
        "Each word has: term, definition, example_sentence, status "
        "(new | learning | mastered).\n\n"
        "**Daily session: learning formats (not exam-only).**\n"
        f"{VOCAB_LEARNING_FORMATS_BLOCK}\n"
        "Wait for their reply before revealing whether they are right.\n"
        "**On wrong / weak answers:** say so briefly, give a short hint (not the full answer), "
        "do NOT say 'word mastered'. For MCQ wrongs: do NOT redisplay choices or a new "
        "```vocab_quiz fence — chips stay on the previous message (up to 3 tries). "
        "After 3 MCQ wrongs: briefly reveal, keep as learning, then a DIFFERENT next word.\n"
        "**On correct / solid answers:** congratulate briefly (mastery is recorded via sync or "
        "MCQ auto-grade), then continue with a DIFFERENT next word in a **different** format "
        "when possible until today's daily_goal is met.\n"
        "Gibberish / unrelated text = wrong.\n"
        "Keep replies short. The lesson UI shows only fences — emit one ```vocab_quiz or "
        "```vocab_card and no vocab lists, check-ins, or markdown essays.\n"
        "Prefer failed/learning words due for review, then new — never re-quiz "
        "✓ mastered as a 'freebie'.\n"
        "Use the **Today:** line in the project snapshot as the only progress counter.\n"
        "When a **Learning path** is listed, teach the current chapter "
        "('Teach only words listed under'). Do NOT invent or add words — "
        "use the preloaded list and its ○ / ◐ / ✓ status.\n\n"
        f"{DAILY_GOAL_COMPLETE_BEHAVIOR}"
    )


LANGUAGE_CHAT_TUTOR_HINT = language_tutor_hint("en")


# Default — chat-based daily sessions (LLM picks format each turn).
LANGUAGE_TUTOR_HINT = LANGUAGE_CHAT_TUTOR_HINT


TRIVIA_QUIZ_FENCE_EXAMPLE = (
    "```vocab_quiz\n"
    '{"quiz_type":"trivia","word":"History",'
    '"question":"Which ancient wonder was a giant statue at the harbor of Rhodes?",'
    '"correct":"A",'
    '"choices":[{"letter":"A","text":"Colossus of Rhodes"},'
    '{"letter":"B","text":"Great Pyramid of Giza"},'
    '{"letter":"C","text":"Hanging Gardens of Babylon"},'
    '{"letter":"D","text":"Lighthouse of Alexandria"}]}\n'
    "```"
)


TRIVIA_QUIZ_FORMAT_BLOCK = (
    "Use this EXACT format for each bonus question:\n"
    f"{TRIVIA_QUIZ_FENCE_EXAMPLE}\n"
    "One question per message. word = topic label (History, Science, …). "
    "Do NOT use spoiler syntax (>! !<), bullet lists of multiple Q&As, or plain-text quizzes. "
    "Wait for the user's A–D before revealing the answer."
)


def _language_tutor_hint(
    _quiz_mode: str | None = None, *, target_language: str | None = "en"
) -> str:
    return language_tutor_hint(target_language)


def _quiz_mode_banner(_quiz_mode: str | None = None, *, kind: str | None = None) -> str:
    del kind
    return (
        "**Presentation mode: chat.** Run today's vocabulary session with mixed learning "
        "formats (teach→use, use→define, occasional MCQ) — one word per turn."
    )


def _level_guidance(level: str) -> str:
    return LEVEL_GUIDANCE.get(level or "level1", LEVEL_GUIDANCE["level1"])


_LEVEL_LABELS: dict[str, str] = {
    "level1": "Beginner",
    "level2": "Elementary",
    "level3": "Intermediate",
    "level4": "Upper intermediate",
    "level5": "Advanced",
    "level6": "Fluent",
}


def _language_progress_line(stats: ProjectStats) -> str:
    if stats.total == 0:
        return "I have no words yet — help me add some first."
    return (
        f"{stats.mastered_count} mastered, {stats.new_count} new, "
        f"{stats.learning_count} learning, {stats.due_for_review} due for review."
    )


def build_language_quiz_prompt(project: Project, stats: ProjectStats) -> str:
    title = project.title.strip()
    lvl = _LEVEL_LABELS.get(project.level or "level1", "Beginner")
    goal = (
        f" {project.description.strip()}."
        if project.description and project.description.strip()
        else ""
    )
    name = language_display_name(getattr(project, "target_language", None))
    return (
        f'Start today\'s vocabulary session for my "{title}" {name} project.\n'
        f"My {name} level: {lvl}.{goal}\n"
        f"{_language_progress_line(stats)}\n\n"
        "Teach and practice one word at a time — mix teach→use (vocab_card then a sentence), "
        "use→define (sentence then open definition), and occasional A–D ```vocab_quiz. "
        "Start with words I failed recently, then new ones — never repeat a word in this session."
    )
