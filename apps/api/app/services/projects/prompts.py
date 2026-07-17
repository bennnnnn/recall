"""Static Learning prompt templates and trivial accessors (no DB)."""

from __future__ import annotations

from app.models.orm import Project
from app.models.schemas import ProjectStats

PROJECT_HINT = (
    "The user keeps **Learning** workspaces — only two kinds:\n"
    "1) **English vocabulary** (`language`) — words, definitions, daily quiz.\n"
    "2) **General knowledge** (`trivia`) — topic facts, daily quiz.\n"
    "Do NOT create learning topics for coding repos, apps to build, math courses, or other subjects.\n"
    "When they ask about learning topics, answer from the injected list below.\n"
    "Creating via chat — name → type (language|trivia) → description → confirm. Changes sync "
    "after your reply; phrase as what you will set up, never claim a project was already "
    "created or updated in this turn.\n"
    "At most ONE English vocabulary project and ONE trivia project per user. "
    "Do NOT create a second — use set_level on the existing one when skill grows.\n"
    "When telling the user their English level, use the plain label only (Beginner, Elementary, "
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


TRIVIA_LEVEL_GUIDANCE: dict[str, str] = {
    "level1": "Easy: well-known facts most adults would recognize from school or pop culture.",
    "level2": "Easy-plus: straightforward facts with one clear correct answer.",
    "level3": "Medium: moderately challenging facts that need some prior knowledge.",
    "level4": "Medium-plus: less obvious facts across the chosen topics.",
    "level5": "Hard: obscure, expert-level, or nuanced facts — still fair multiple-choice.",
    "level6": "Expert: very difficult facts; wrong answers should be plausible distractors.",
}


VOCAB_QUIZ_MARKDOWN_EXAMPLE = (
    "**Word:** apple\nWhat does it mean?\nA) a red fruit\nB) a vehicle\nC) a feeling\nD) a color"
)


VOCAB_QUIZ_FENCE_EXAMPLE = (
    "```vocab_quiz\n"
    '{"word":"apple","question":"What does it mean?",'
    '"correct":"A",'
    '"choices":[{"letter":"A","text":"a red fruit"},{"letter":"B","text":"a vehicle"},'
    '{"letter":"C","text":"a feeling"},{"letter":"D","text":"a color"}]}\n'
    "```"
)


VOCAB_QUIZ_FORMAT_BLOCK = (
    f"{VOCAB_QUIZ_MARKDOWN_EXAMPLE}\n\n"
    f"Then append this machine-readable block (required — include correct letter A–D):\n"
    f"{VOCAB_QUIZ_FENCE_EXAMPLE}"
)


VOCAB_CARD_FENCE_EXAMPLE = (
    '```vocab_card\n{"word":"serendipity","definition":"finding something good by accident"}\n```'
)


# Learning-oriented rotation for vocabulary (trivia stays MCQ-only).
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


LANGUAGE_CHAT_TUTOR_HINT = (
    "Active **language** project — **daily vocabulary in chat**.\n"
    "The project **level** is the user's **English skill level** (level1=beginner … level6=fluent).\n"
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
    "Keep replies short. Prefer failed/learning words due for review, then new — never re-quiz "
    "✓ mastered as a 'freebie'.\n"
    "Use the **Today:** line in the project snapshot as the only progress counter.\n\n"
    f"{DAILY_GOAL_COMPLETE_BEHAVIOR}"
)


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


TRIVIA_BONUS_QUIZ_RULES = (
    "**Bonus quiz (after today's goal):** When the user explicitly asks for more quiz, bonus "
    "questions, or extra practice beyond today's goal, ask ONE multiple-choice question per turn "
    "using ```vocab_quiz JSON with quiz_type trivia:\n"
    f"{TRIVIA_QUIZ_FORMAT_BLOCK}"
)


TRIVIA_CHAT_TUTOR_HINT = (
    "Active **trivia** project — **daily general knowledge in chat**.\n"
    "Topics are in project description (comma-separated). daily_goal = correct/mastered per session.\n\n"
    "**Daily session format (required): multiple choice only.**\n"
    "One question per turn. Every question MUST use ```vocab_quiz JSON with quiz_type trivia "
    "(word = topic label such as History, Science):\n"
    f"{TRIVIA_QUIZ_FORMAT_BLOCK}\n"
    "Wait for A–D before revealing the answer.\n"
    "**On wrong answers:** say wrong, give a short hint (not the full answer), do NOT mark "
    "mastered, and do NOT redisplay the question or emit a new ```vocab_quiz fence — they will "
    "answer again on the previous chips (up to 3 tries). After 3 wrong tries: briefly reveal "
    "the answer, keep it as learning/missed for next time, then ask a DIFFERENT next question — "
    "never re-ask the missed question in this session.\n"
    "**On correct answers:** congratulate briefly (mastering is recorded automatically), then "
    "ask the NEXT question.\n"
    "Do NOT use vocab_card or teach English vocabulary.\n"
    "Stop when today's daily_goal is met unless they ask for bonus practice.\n"
    "Use the **Today:** line as the only progress counter. If the quiz pool is empty, invent a "
    "new question on the project's topics.\n\n"
    f"{TRIVIA_BONUS_QUIZ_RULES}\n\n"
    f"{DAILY_GOAL_COMPLETE_BEHAVIOR}"
)


TRIVIA_TUTOR_HINT = TRIVIA_CHAT_TUTOR_HINT


def _language_tutor_hint(_quiz_mode: str | None = None) -> str:
    return LANGUAGE_CHAT_TUTOR_HINT


def _trivia_tutor_hint(_quiz_mode: str | None = None) -> str:
    return TRIVIA_CHAT_TUTOR_HINT


def _quiz_mode_banner(_quiz_mode: str | None = None, *, kind: str | None = None) -> str:
    if kind == "trivia":
        return (
            "**Presentation mode: chat.** Run today's trivia as multiple-choice only — "
            "one ```vocab_quiz question per turn (quiz_type trivia)."
        )
    return (
        "**Presentation mode: chat.** Run today's vocabulary session with mixed learning "
        "formats (teach→use, use→define, occasional MCQ) — one word per turn."
    )


def _level_guidance(level: str) -> str:
    return LEVEL_GUIDANCE.get(level or "level1", LEVEL_GUIDANCE["level1"])


def _trivia_level_guidance(level: str) -> str:
    return TRIVIA_LEVEL_GUIDANCE.get(level or "level1", TRIVIA_LEVEL_GUIDANCE["level1"])


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
    return (
        f'Start today\'s vocabulary session for my "{title}" English project.\n'
        f"My English level: {lvl}.{goal}\n"
        f"{_language_progress_line(stats)}\n\n"
        "Teach and practice one word at a time — mix teach→use (vocab_card then a sentence), "
        "use→define (sentence then open definition), and occasional A–D ```vocab_quiz. "
        "Start with words I failed recently, then new ones — never repeat a word in this session."
    )
