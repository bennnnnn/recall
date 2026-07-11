import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Project, ProjectItem, User
from app.models.schemas import (
    ProjectActionItem,
    ProjectExtractionResult,
    ProjectItemOut,
    ProjectListGroup,
    ProjectStats,
)
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services.vocab_quiz import QuizAnswerGrade

logger = logging.getLogger(__name__)


async def _invalidate_home_for_user(user_id: UUID) -> None:
    """Home cards depend on project stats — bust cache after learning mutations."""
    from app.services import home as home_service

    await home_service.invalidate_home_cache(user_id)


# Defensive caps for LLM-inferred project mutations applied from a transcript.
MAX_PROJECT_ACTIONS_PER_TURN = 3
# Whole-project / whole-deck deletes are too destructive to apply from a model's
# interpretation of chat text — the user must remove those explicitly.
PROJECT_BLOCKED_FROM_TRANSCRIPT = frozenset({"delete_project", "delete_list"})

DEFAULT_LIST = "General"

# Product surface: English vocabulary + general knowledge only.
LEARNING_PRODUCT_KINDS = frozenset({"language", "trivia"})
LEARNING_KIND_ALIASES = {"vocabulary": "language"}


def normalize_project_kind(kind: str) -> str:
    """Map write aliases (vocabulary → language); leave unknown kinds unchanged."""
    return LEARNING_KIND_ALIASES.get(kind, kind)


def is_learning_product_kind(kind: str) -> bool:
    return normalize_project_kind(kind) in LEARNING_PRODUCT_KINDS


_PROJECT_SYNC_TRANSCRIPT = re.compile(
    r"\b("
    r"learning topic|vocab(?:ulary)?|add(?:ed)? (?:word|words)|"
    r"master(?:ed)?|quiz|flashcard|"
    r"set_level|trivia|general knowledge|"
    r"save (?:to|this)|new list|word list|"
    r"create (?:a )?(?:learning )?(?:topic|project)"
    r")\b",
    re.IGNORECASE,
)


def transcript_implies_project_sync(
    transcript: str,
    *,
    chat_project_id: UUID | None = None,
) -> bool:
    """Skip project-extraction jobs on unrelated chit-chat."""
    if chat_project_id is not None:
        return True
    text = transcript.strip()
    if not text:
        return False
    return bool(_PROJECT_SYNC_TRANSCRIPT.search(text))


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
    "**Bonus quiz (after today's goal):** When the user explicitly asks for more quiz, bonus "
    "words, or extra practice beyond today's goal, ask ONE multiple-choice question per turn "
    "using ```vocab_quiz JSON:\n"
    f"{VOCAB_QUIZ_FORMAT_BLOCK}\n"
    "One question per message. Do NOT use spoiler syntax (>! !<) or bullet lists of Q&As. "
    "Wait for A–D before revealing the answer."
)

LANGUAGE_CHAT_TUTOR_HINT = (
    "Active **language** project — **daily vocabulary in chat**.\n"
    "The project **level** is the user's **English skill level** (level1=beginner … level6=fluent).\n"
    "Each word has: term, definition, example_sentence, status "
    "(new | learning | mastered).\n\n"
    "**Daily session format (required): multiple choice only.**\n"
    "One word per turn. Do NOT teach the definition before asking. Do NOT ask open-ended "
    "'what does it mean?' without A–D choices.\n"
    "Every question MUST include a readable A–D list AND a ```vocab_quiz JSON fence with the "
    "correct letter (required for tap-to-answer chips and server grading):\n"
    f"{VOCAB_QUIZ_FORMAT_BLOCK}\n"
    "Wait for their letter before revealing the answer.\n"
    "**On wrong answers:** say wrong, give a short hint (not the full definition / correct "
    "letter), do NOT say 'word mastered', and do NOT redisplay the question or emit a new "
    "```vocab_quiz fence — they will answer again on the previous chips (up to 3 tries). "
    "After 3 wrong tries: briefly reveal the answer, keep it as learning/missed for next time, "
    "then ask a DIFFERENT next word — never re-ask the missed word in this session.\n"
    "**On correct answers:** congratulate briefly (mastering is recorded automatically), then "
    "ask the NEXT word until today's daily_goal is met.\n"
    "Gibberish / unrelated text / random letters other than A–D = wrong.\n"
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
        "**Presentation mode: chat.** Run today's vocabulary session as multiple-choice only — "
        "one ```vocab_quiz question per turn (readable A–D + JSON fence)."
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
        "Quiz me with multiple-choice ```vocab_quiz only (A-D). "
        "Start with words I failed recently, then new ones — never repeat a word in this session."
    )


def _format_missed_quiz_lines(items: list[ProjectItem], *, limit: int = 30) -> list[str]:
    learning = [item for item in items if _item_status(item) == "learning"]
    if not learning:
        return []
    lines = [
        "\nStill learning / failed recently — prefer a NEW item next in this session; "
        "bring these back on a later day (do NOT re-ask the one just missed):"
    ]
    for item in learning[:limit]:
        missed_at = getattr(item, "last_incorrect_at", None)
        when = (
            missed_at.astimezone(UTC).date().isoformat()
            if isinstance(missed_at, datetime)
            else "recent"
        )
        detail = (item.definition or item.note or item.example_sentence or "").strip()
        suffix = f" — {detail[:120]}" if detail else ""
        lines.append(f"- {item.content}{suffix} (missed {when})")
    return lines


# Misses stay out of the "quiz FIRST today" list until SM-2 due (usually next day),
# so a mid-session miss is not immediately re-prioritized against "never re-ask".
_FAILED_REVIEW_FALLBACK_MIN_AGE = timedelta(hours=12)


def _format_failed_review_lines(items: list[ProjectItem], *, limit: int = 12) -> list[str]:
    """Session-start nudge: bring back due failed items first (not same-session misses)."""
    now = datetime.now(UTC)
    failed: list[ProjectItem] = []
    for item in items:
        if _item_status(item) != "learning":
            continue
        missed = getattr(item, "last_incorrect_at", None)
        if not isinstance(missed, datetime):
            continue
        missed_utc = missed.astimezone(UTC) if missed.tzinfo else missed.replace(tzinfo=UTC)
        due = getattr(item, "due_at", None)
        if isinstance(due, datetime):
            due_utc = due.astimezone(UTC) if due.tzinfo else due.replace(tzinfo=UTC)
            if due_utc > now:
                continue
        elif now - missed_utc < _FAILED_REVIEW_FALLBACK_MIN_AGE:
            continue
        failed.append(item)
    if not failed:
        return []

    def _miss_key(item: ProjectItem) -> datetime:
        missed = getattr(item, "last_incorrect_at", None)
        if isinstance(missed, datetime):
            return missed.astimezone(UTC) if missed.tzinfo else missed.replace(tzinfo=UTC)
        return datetime.min.replace(tzinfo=UTC)

    failed.sort(key=_miss_key, reverse=True)
    lines = [
        "\n**Failed and due for review — quiz these FIRST today** (then new words). "
        "Do not skip them for brand-new items. Do not re-ask a word already missed "
        "earlier in this same session:"
    ]
    for item in failed[:limit]:
        lines.append(f"- {item.content}")
    return lines


def _format_covered_quiz_lines(
    items: list[ProjectItem],
    *,
    just_answered: str | None = None,
    limit: int = 25,
) -> list[str]:
    """Tell the model which facts/words are done so it does not loop the same question."""
    covered: list[str] = []
    seen: set[str] = set()
    if just_answered:
        key = just_answered.strip().lower()
        if key:
            covered.append(just_answered.strip())
            seen.add(key)
    mastered = [item for item in items if _item_status(item) == "mastered"]

    def _covered_sort_key(item: ProjectItem) -> datetime:
        for attr in ("mastered_at", "last_reviewed_at", "created_at"):
            value = getattr(item, attr, None)
            if isinstance(value, datetime):
                return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.min.replace(tzinfo=UTC)

    mastered.sort(key=_covered_sort_key, reverse=True)
    for item in mastered:
        text = (item.content or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        covered.append(text)
        if len(covered) >= limit:
            break
    if not covered:
        return []
    lines = ["\nAlready covered — do NOT ask these again in this session:"]
    lines.extend(f"- {text}" for text in covered)
    return lines


async def load_project_quiz_context(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    settings: Settings,
    *,
    quiz_grade: QuizAnswerGrade | None = None,
) -> str:
    """Lightweight tutor slice for quiz answer turns — level, pool, and card format."""
    from app.services.vocab_quiz import MAX_QUIZ_TRIES_PER_QUESTION

    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None:
        return ""

    retry_same = (
        quiz_grade is not None and not quiz_grade.is_correct and not quiz_grade.tries_exhausted
    )
    just_correct = quiz_grade is not None and quiz_grade.is_correct
    tries_exhausted = quiz_grade is not None and quiz_grade.tries_exhausted
    answered_label = ""
    attempt = quiz_grade.attempt if quiz_grade is not None else 1
    if quiz_grade is not None:
        # Trivia: question text; vocab: the word.
        answered_label = (
            (quiz_grade.question or quiz_grade.word)
            if quiz_grade.quiz_type == "trivia"
            else quiz_grade.word
        ).strip()

    if _is_trivia_project(project):
        items = await project_items_repo.list_for_user(
            session,
            user_id,
            project_id=project_id,
            limit=settings.project_item_inject_limit,
        )
        if retry_same and answered_label:
            follow = (
                f'WRONG on "{answered_label}" (try {attempt}/{MAX_QUIZ_TRIES_PER_QUESTION}) — '
                "reply with brief feedback + a short hint only. "
                "Do NOT redisplay the question, choices, or a ```vocab_quiz fence. "
                "Never switch to vocabulary words."
            )
        elif tries_exhausted and answered_label:
            follow = (
                f'MISSED after {attempt} tries — "{answered_label}" stays learning for next time. '
                "Briefly reveal the correct answer, then ask a DIFFERENT next general-knowledge "
                'question (quiz_type trivia — never vocabulary / "what does X mean?"):'
            )
        elif just_correct and answered_label:
            follow = (
                f'CORRECT — "{answered_label}" is done. Do NOT repeat that question. '
                "Ask a DIFFERENT next general-knowledge question using this format "
                '(quiz_type trivia only — never vocabulary / "what does X mean?"):'
            )
        else:
            follow = (
                "CORRECT (or starting) — after brief feedback, ask the NEXT general-knowledge "
                "question using this format (quiz_type trivia only — never vocabulary/"
                '"what does X mean?"). Never repeat a question already asked in this chat.'
            )
        lines = [
            f"Active trivia quiz — project: {project.title}.",
            f"Daily goal: {_trivia_daily_goal(project)} correct answers per session.",
            follow,
        ]
        if not retry_same:
            lines.extend(
                [
                    f"{TRIVIA_QUIZ_FENCE_EXAMPLE}",
                    "Correct answers are saved automatically. Never master on a wrong answer.",
                ]
            )
        else:
            lines.append("Correct answers are saved automatically. Never master on a wrong answer.")
        if just_correct or tries_exhausted or not retry_same:
            lines.extend(_format_covered_quiz_lines(items, just_answered=answered_label or None))
        if retry_same or tries_exhausted:
            lines.extend(_format_missed_quiz_lines(items))
        return "\n".join(lines)
    if not _is_language_project(project):
        return ""
    items = await project_items_repo.list_for_user(
        session,
        user_id,
        project_id=project_id,
        limit=settings.project_item_inject_limit,
    )
    # Exclude the word they just got right / exhausted even if the session snapshot is briefly stale.
    quiz_pool = [
        i
        for i in items
        if _item_status(i) in ("new", "learning")
        and not (
            (just_correct or tries_exhausted)
            and answered_label
            and (i.content or "").strip().lower() == answered_label.lower()
        )
    ]
    level = project.level or "level1"
    if retry_same and answered_label:
        follow = (
            f'WRONG on "{answered_label}" (try {attempt}/{MAX_QUIZ_TRIES_PER_QUESTION}) — '
            "reply with brief feedback + a short hint only. "
            "Do NOT redisplay the question, choices, or a ```vocab_quiz fence."
        )
    elif tries_exhausted and answered_label:
        follow = (
            f'MISSED after {attempt} tries — "{answered_label}" stays learning for next time. '
            "Briefly reveal the correct answer, then ask a DIFFERENT next word using the same "
            "card format:"
        )
    elif just_correct and answered_label:
        follow = (
            f'CORRECT — "{answered_label}" is done. Do NOT re-ask that word. '
            "Ask a DIFFERENT next word using the same card format:"
        )
    else:
        follow = (
            "CORRECT (or starting) — after brief feedback, ask the NEXT word using "
            "the same card format. Never repeat a word already mastered in this session."
        )
    lines = [
        f"Active vocabulary quiz — project: {project.title} ({_LEVEL_LABELS.get(level, level)}).",
        f"English skill: {_level_guidance(level)}",
        follow,
    ]
    if not retry_same:
        lines.extend(
            [
                VOCAB_QUIZ_FORMAT_BLOCK,
                "Pick words only from new/learning items at this level (except when re-asking a miss).",
                "Correct answers are saved automatically. Never master on a wrong answer.",
            ]
        )
    else:
        lines.append("Correct answers are saved automatically. Never master on a wrong answer.")
    if quiz_pool and not retry_same:
        lines.append("\nNew/learning words available:")
        for item in quiz_pool[:40]:
            lines.append(f"- {item.content}")
    elif just_correct or tries_exhausted:
        lines.append(
            "\nNo new/learning words left in the pool — invent a NEW word at this level "
            "(not one already covered)."
        )
    if just_correct or tries_exhausted or not retry_same:
        lines.extend(_format_covered_quiz_lines(items, just_answered=answered_label or None))
    if retry_same or tries_exhausted:
        lines.extend(_format_missed_quiz_lines(items))
    return "\n".join(lines)


_VOCAB_QUESTION_MARKERS = re.compile(
    r"(?:"
    r"What does .+ mean\??|"
    r"Which sentence uses|"
    r"use .+ in a sentence|"
    r"Reply with (?:the )?letter|"
    r"\bA\)\s|"
    r"\bB\)\s|"
    r"```vocab_quiz"
    r")",
    re.IGNORECASE,
)


def looks_like_vocab_question(content: str) -> bool:
    """Heuristic: prior assistant turn was asking a vocab/trivia question."""
    if not content or not content.strip():
        return False
    tail = content.strip()[-1200:]
    if _VOCAB_QUESTION_MARKERS.search(tail):
        return True
    if re.search(r"\*\*[^*\n]{2,40}\*\*", tail) and "?" in tail[-400:]:
        return True
    return False


def _recently_missed_quiz(item: ProjectItem, *, within_seconds: int = 86_400) -> bool:
    """Block sync-master for a day after a miss so failed words stay learning."""
    missed = getattr(item, "last_incorrect_at", None)
    if not isinstance(missed, datetime):
        return False
    return (datetime.now(UTC) - missed.astimezone(UTC)).total_seconds() < within_seconds


async def _persist_quiz_outcome(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    chat_id: UUID,
    existing: ProjectItem | None,
    content: str,
    list_title: str,
    is_correct: bool,
) -> None:
    """Record a graded answer on the matched item, creating it on first sight.

    Shared ledger write for the trivia and vocab branches; the commit stays
    with the caller's outer transaction (commit=False throughout).
    """
    item = existing
    if item is None:
        item = await project_items_repo.create(
            session,
            user_id=user_id,
            project_id=project_id,
            content=content,
            list_title=list_title,
            chat_id=chat_id,
            status="new",
            commit=False,
        )
    await project_items_repo.apply_quiz_result(session, item, is_correct=is_correct, commit=False)


async def apply_deterministic_quiz_answer(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    project_id: UUID | None,
    assistant_content: str,
    user_answer: str,
    topic_hint: str | None = None,
    question_hint: str | None = None,
    is_correct_hint: bool | None = None,
    attempt: int = 1,
) -> QuizAnswerGrade | None:
    """Persist quiz results without waiting on background LLM project sync."""
    from app.services import vocab_quiz as vocab_quiz_service

    quiz = vocab_quiz_service.parse_vocab_quiz(assistant_content)
    choices = quiz.choices if quiz is not None else ()
    letter = vocab_quiz_service.quiz_answer_letter(user_answer, choices=choices)
    if letter is None:
        return None

    if quiz is None and topic_hint and question_hint:
        from app.services.vocab_quiz import ParsedVocabQuiz

        quiz = ParsedVocabQuiz(
            word=topic_hint.strip(),
            question=question_hint.strip(),
            correct=None,
            quiz_type="trivia",
        )
    if quiz is None:
        return None

    # Only score in project-linked chats — never guess trivia/vocab project from user id.
    if project_id is None:
        return None

    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None:
        return None

    is_trivia = _is_trivia_project(project) or quiz.quiz_type == "trivia"
    is_correct: bool | None = None
    if quiz.correct:
        is_correct = letter == quiz.correct.upper()
    elif is_correct_hint is not None:
        is_correct = is_correct_hint
    if is_correct is None:
        return None
    correct_letter = (quiz.correct or "").upper()
    if not re.fullmatch(r"[A-D]", correct_letter):
        return None

    try_number = max(1, attempt)
    tries_exhausted = (not is_correct) and (
        try_number >= vocab_quiz_service.MAX_QUIZ_TRIES_PER_QUESTION
    )
    # Persist correct immediately; persist misses only after 3 wrong tries.
    should_persist = is_correct or tries_exhausted

    if is_trivia:
        topic = quiz.word.strip()
        question = (quiz.question or quiz.word).strip()
        if not question:
            return None
        list_title = topic or DEFAULT_LIST
        items = await project_items_repo.find_quiz_candidates(
            session, user_id, project.id, question
        )
        existing = _find_item(items, project.id, list_title, question)
        if should_persist:
            await _persist_quiz_outcome(
                session,
                user_id=user_id,
                project_id=project.id,
                chat_id=chat_id,
                existing=existing,
                content=question,
                list_title=list_title,
                is_correct=is_correct,
            )
        return vocab_quiz_service.QuizAnswerGrade(
            is_correct=is_correct,
            user_letter=letter,
            correct_letter=correct_letter,
            # Feedback label = correct choice text (not the topic like "History").
            word=(quiz.correct_text or question)[:80],
            quiz_type="trivia",
            question=question,
            attempt=try_number,
            tries_exhausted=tries_exhausted,
        )

    if not _is_language_project(project):
        return None

    word = quiz.word.strip()
    if not word:
        return None
    list_title = DEFAULT_LIST
    items = await project_items_repo.find_quiz_candidates(session, user_id, project.id, word)
    existing = _find_item(items, project.id, list_title, word) or _find_item_by_content(
        items, project.id, word
    )
    if should_persist:
        await _persist_quiz_outcome(
            session,
            user_id=user_id,
            project_id=project.id,
            chat_id=chat_id,
            existing=existing,
            content=word,
            list_title=list_title,
            is_correct=is_correct,
        )
    return vocab_quiz_service.QuizAnswerGrade(
        is_correct=is_correct,
        user_letter=letter,
        correct_letter=correct_letter,
        word=word,
        quiz_type="vocab",
        question=quiz.question,
        attempt=try_number,
        tries_exhausted=tries_exhausted,
    )


def _resolve_list_title(project: Project, action: ProjectActionItem) -> str:
    return action.list_title.strip() or DEFAULT_LIST


def _item_status(item: ProjectItem) -> str:
    if item.status:
        return item.status
    return "mastered" if item.mastered else "new"


def _find_item_by_content(
    items: list[ProjectItem], project_id: UUID, content: str
) -> ProjectItem | None:
    needle = _normalize(content)
    for item in items:
        if item.project_id == project_id and _normalize(item.content) == needle:
            return item
    return None


def _is_language_project(project: Project) -> bool:
    return project.kind in ("language", "vocabulary")


def _is_trivia_project(project: Project) -> bool:
    return project.kind == "trivia"


def _trivia_daily_goal(project: Project) -> int:
    goal = getattr(project, "daily_goal", None)
    if isinstance(goal, int) and goal >= 1:
        return goal
    return DEFAULT_DAILY_VOCAB_GOAL


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _list_key(list_title: str) -> str:
    return _normalize(list_title or DEFAULT_LIST)


def _find_language_project(
    projects: list[Project],
    target_language: str = "en",
) -> Project | None:
    lang = (target_language or "en").strip().lower()
    for project in projects:
        if (
            _is_language_project(project)
            and (project.target_language or "en").strip().lower() == lang
        ):
            return project
    return None


def _find_project(projects: list[Project], title: str) -> Project | None:
    needle = _normalize(title)
    if not needle:
        return projects[0] if len(projects) == 1 else None
    for project in projects:
        if _normalize(project.title) == needle:
            return project
    for project in projects:
        if needle in _normalize(project.title) or _normalize(project.title) in needle:
            return project
    if len(projects) == 1:
        return projects[0]
    return None


def _find_item(
    items: list[ProjectItem],
    project_id: UUID,
    list_title: str,
    content: str,
    *,
    mastered_only: bool | None = None,
) -> ProjectItem | None:
    needle = _normalize(content)
    list_norm = _list_key(list_title)
    candidates = [
        i for i in items if i.project_id == project_id and _list_key(i.list_title) == list_norm
    ]
    if mastered_only is True:
        candidates = [i for i in candidates if _item_status(i) == "mastered"]
    elif mastered_only is False:
        candidates = [i for i in candidates if _item_status(i) != "mastered"]
    if not candidates:
        candidates = [i for i in items if i.project_id == project_id]
    for item in candidates:
        if _normalize(item.content) == needle:
            return item
    for item in candidates:
        if needle in _normalize(item.content) or _normalize(item.content) in needle:
            return item
    return None


DEFAULT_DAILY_VOCAB_GOAL = 10


def _language_daily_goal(project: Project) -> int:
    goal = getattr(project, "daily_goal", None)
    if isinstance(goal, int) and goal >= 1:
        return goal
    return DEFAULT_DAILY_VOCAB_GOAL


def format_projects_block(projects: list[Project], items: list[ProjectItem]) -> str:
    if not projects:
        return ""
    by_project: dict[UUID, list[ProjectItem]] = {}
    for item in items:
        by_project.setdefault(item.project_id, []).append(item)

    lines = ["User learning topics (title, type, lists, and study progress):"]
    for project in sorted(projects, key=lambda p: p.title.casefold()):
        project_items = by_project.get(project.id, [])
        stats = _stats_for_items(project_items)
        desc = f" — {project.description}" if project.description else ""
        level = getattr(project, "level", "level1") or "level1"
        guidance = _level_guidance(level)
        meta = project.kind
        if _is_language_project(project):
            meta = f"{project.kind}, {level}"
        elif _is_trivia_project(project):
            meta = f"{project.kind}, topics={project.description or 'general'}"
        skill_line = ""
        if _is_language_project(project):
            skill_line = (
                f"English skill: {guidance}\n"
                f"Daily goal: {_language_daily_goal(project)} new words per session\n"
            )
        elif _is_trivia_project(project):
            skill_line = (
                f"Daily quiz goal: {_trivia_daily_goal(project)} correct answers per session\n"
                f"Topics: {project.description or 'general'}\n"
            )
        lines.append(
            f"\n### {project.title} ({meta}){desc}\n"
            f"{skill_line}"
            f"Progress: {stats['mastered_count']}/{stats['total']} mastered, "
            f"{stats['new_count']} new, {stats['learning_count']} learning, "
            f"{stats['added_this_week']} added this week, "
            f"{stats['due_for_review']} due for review"
        )
        if not project_items:
            lines.append("- (no words yet)")
            continue
        by_list: dict[str, list[ProjectItem]] = {}
        for item in project_items:
            lst = item.list_title.strip() or DEFAULT_LIST
            by_list.setdefault(lst, []).append(item)
        if _is_language_project(project):
            for list_title in sorted(by_list.keys(), key=str.casefold):
                lines.append(f"\n#### {list_title}")
                for item in by_list[list_title]:
                    lines.append(_format_vocab_line(item))
            continue
        for list_title in sorted(by_list.keys(), key=str.casefold):
            lines.append(f"\n#### {list_title}")
            for item in by_list[list_title]:
                mark = "✓" if item.mastered else "○"
                status = "mastered" if item.mastered else "learning"
                note_suffix = f' — e.g. "{item.note}"' if item.note else ""
                lines.append(f"- {mark} {item.content} ({status}{note_suffix})")
    return "\n".join(lines)


def _format_vocab_line(item: ProjectItem) -> str:
    status = _item_status(item)
    mark = "✓" if status == "mastered" else ("◐" if status == "learning" else "○")
    defn = f" — {item.definition}" if item.definition else ""
    example = item.example_sentence or item.note
    ex = f' e.g. "{example}"' if example else ""
    return f"- {mark} {item.content}{defn}{ex} ({status})"


def _stats_for_items(items: list[ProjectItem]) -> dict[str, int]:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    due_cutoff = now - timedelta(hours=24)
    stats = {
        "total": len(items),
        "new_count": 0,
        "learning_count": 0,
        "mastered_count": 0,
        "added_this_week": 0,
        "due_for_review": 0,
    }
    for item in items:
        status = _item_status(item)
        if status == "mastered":
            stats["mastered_count"] += 1
        elif status == "learning":
            stats["learning_count"] += 1
        else:
            stats["new_count"] += 1
        created = item.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if created >= week_ago:
            stats["added_this_week"] += 1
        status = _item_status(item)
        if status == "new":
            stats["due_for_review"] += 1
        elif status == "learning":
            if item.last_reviewed_at is None:
                stats["due_for_review"] += 1
            else:
                reviewed = item.last_reviewed_at
                if reviewed.tzinfo is None:
                    reviewed = reviewed.replace(tzinfo=UTC)
                if reviewed <= due_cutoff:
                    stats["due_for_review"] += 1
    return stats


def _format_today_session_line(project: Project, stats: dict[str, int]) -> str:
    from app.services import daily_learning

    daily_goal = daily_learning.resolve_daily_goal(project)
    mastered_today = int(stats.get("mastered_today") or 0)
    missed_today = int(stats.get("missed_today") or 0)
    completed_today = mastered_today + missed_today
    remaining = max(0, daily_goal - completed_today)
    if completed_today >= daily_goal:
        return (
            f"**Today:** {completed_today}/{daily_goal} done — daily goal complete "
            f"({mastered_today} correct, {missed_today} missed). "
            "This is the authoritative progress line — do not restate or contradict it."
        )
    return (
        f"**Today:** {completed_today}/{daily_goal} done "
        f"({mastered_today} correct, {missed_today} missed; {remaining} more needed). "
        "This is the authoritative progress line — do not restate or contradict it."
    )


def _quiz_pool_items(items: list[ProjectItem]) -> tuple[list[ProjectItem], int]:
    pool = [i for i in items if _item_status(i) != "mastered"]
    return pool, len(items) - len(pool)


def _quiz_pool_note(project: Project, pool: list[ProjectItem], mastered_skip: int) -> str:
    if mastered_skip <= 0:
        return ""
    if pool:
        return (
            f"\n\n({mastered_skip} already-mastered items omitted above — do not re-quiz them "
            "in today's session unless the user asks for review.)"
        )
    if _is_trivia_project(project):
        topics = project.description or "general knowledge"
        return (
            "\n\n**Quiz pool:** all saved facts are mastered. Ask a **new** question from "
            f"topics ({topics}) — not a repeat of previously learned facts."
        )
    return (
        "\n\n**Quiz pool:** all saved words are mastered. Teach/quiz **new** words at the "
        "user's level toward today's goal."
    )


async def load_project_for_prompt(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    settings: Settings,
    *,
    quiz_mode: str | None = None,
    client_timezone: str | None = None,
) -> str:
    from app.repositories import users as users_repo
    from app.services import time_context as time_context_service

    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None:
        return ""
    items = await project_items_repo.list_for_user(
        session,
        user_id,
        project_id=project_id,
        limit=settings.project_item_inject_limit,
    )
    display_items = items
    pool_note = ""
    if quiz_mode != "exam" and (_is_language_project(project) or _is_trivia_project(project)):
        pool, mastered_skip = _quiz_pool_items(items)
        if mastered_skip > 0:
            display_items = pool
            pool_note = _quiz_pool_note(project, pool, mastered_skip)
    block = format_projects_block([project], display_items)
    if pool_note:
        block = f"{block}{pool_note}"
    if _is_language_project(project) or _is_trivia_project(project):
        failed_lines = _format_failed_review_lines(items)
        if failed_lines:
            block = f"{block}{''.join(failed_lines)}"
    today_line = ""
    if _is_language_project(project) or _is_trivia_project(project):
        user = await users_repo.get_by_id(session, user_id)
        tz_name = time_context_service.effective_timezone(
            user.timezone if user else None,
            client_timezone,
        )
        stats = await project_items_repo.count_stats(
            session,
            project_id,
            user_id,
            timezone_name=tz_name,
        )
        today_line = _format_today_session_line(project, stats)
    if _is_language_project(project):
        hint = _language_tutor_hint(quiz_mode)
        if today_line:
            hint = f"{today_line}\n\n{hint}"
        block = f"{block}\n\n{hint}" if block else hint
    if _is_trivia_project(project):
        hint = _trivia_tutor_hint(quiz_mode)
        level_line = f"Trivia difficulty: {_trivia_level_guidance(project.level or 'level1')}"
        hint = f"{level_line}\n\n{hint}"
        if today_line:
            hint = f"{today_line}\n\n{hint}"
        block = f"{block}\n\n{hint}" if block else hint
    if block:
        block = (
            "This chat is linked to ONE learning topic — focus on it unless the user "
            f"explicitly asks about something else.\n\n"
            f"{_quiz_mode_banner(quiz_mode, kind=project.kind)}\n\n{block}"
        )
    return block


async def load_projects_for_prompt(
    session: AsyncSession,
    user_id: UUID,
    settings: Settings,
) -> str:
    projects = await projects_repo.list_for_user(
        session, user_id, limit=settings.project_inject_limit
    )
    if not projects:
        return ""
    project_ids = [p.id for p in projects]
    items = await project_items_repo.list_for_user(
        session,
        user_id,
        project_ids=project_ids,
        limit=settings.project_item_inject_limit,
    )
    block = format_projects_block(projects, items)
    if any(_is_language_project(p) for p in projects):
        block = f"{block}\n\n{LANGUAGE_TUTOR_HINT}" if block else LANGUAGE_TUTOR_HINT
    if any(_is_trivia_project(p) for p in projects):
        block = f"{block}\n\n{TRIVIA_TUTOR_HINT}" if block else TRIVIA_TUTOR_HINT
    return block


def _daily_learning_quiz_label(project: Project) -> tuple[str, str]:
    """Return (quiz_type_label, progress_unit) for prompt injection."""
    if _is_language_project(project):
        return "vocabulary quiz", "words mastered today"
    return "general knowledge quiz", "correct answers today"


async def load_daily_learning_summary_for_prompt(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    client_timezone: str | None = None,
) -> str:
    """Compact today-only stats for day-planning turns (not full word lists)."""
    from app.services import daily_learning
    from app.services import time_context as time_context_service

    projects = await projects_repo.list_for_user(
        session, user.id, limit=settings.project_inject_limit
    )
    tz_name = time_context_service.effective_timezone(user.timezone, client_timezone)
    learning_projects = [
        project
        for project in projects
        if _is_language_project(project) or _is_trivia_project(project)
    ]
    if not learning_projects:
        return ""
    stats_by_project = await project_items_repo.count_stats_by_project(
        session,
        [project.id for project in learning_projects],
        timezone_by_project={project.id: tz_name for project in learning_projects},
    )
    lines: list[str] = []
    for project in learning_projects:
        stats = stats_by_project.get(project.id, {})
        total = int(stats.get("total") or 0)
        daily_goal = daily_learning.resolve_daily_goal(project)
        mastered_today = int(stats.get("mastered_today") or 0)
        missed_today = int(stats.get("missed_today") or 0)
        completed_today = mastered_today + missed_today
        if completed_today >= daily_goal:
            continue
        quiz_label, unit = _daily_learning_quiz_label(project)
        remaining = max(0, daily_goal - completed_today)
        if total == 0:
            status = f"not started — {remaining} left for today's {quiz_label}"
        elif completed_today == 0:
            status = f"not started — {remaining} left for today's {quiz_label}"
        else:
            status = f"{remaining} left for today's {quiz_label}"
        lines.append(
            f"- {project.title} ({quiz_label}): {completed_today}/{daily_goal} done "
            f"({mastered_today} correct, {missed_today} missed; {status})"
        )
    if not lines:
        return ""
    return "Today's learning progress (local calendar day, authoritative):\n" + "\n".join(lines)


def group_items(items: list[ProjectItem]) -> list[ProjectListGroup]:
    by_list: dict[str, list[ProjectItem]] = {}
    for item in items:
        lst = item.list_title.strip() or DEFAULT_LIST
        by_list.setdefault(lst, []).append(item)
    groups: list[ProjectListGroup] = []
    for list_title in sorted(by_list.keys(), key=str.casefold):
        groups.append(
            ProjectListGroup(
                list_title=list_title,
                items=[ProjectItemOut.model_validate(i) for i in by_list[list_title]],
            )
        )
    return groups


def group_trivia_items(items: list[ProjectItem]) -> list[ProjectListGroup]:
    """Group saved quiz facts by topic (list_title)."""
    return group_items(items)


def build_stats(items: list[ProjectItem]) -> ProjectStats:
    raw = _stats_for_items(items)
    return ProjectStats.model_validate(raw)


def _build_enriched_stats(
    project: Project,
    items: list[ProjectItem],
    *,
    timezone_name: str,
    daily_goal_history: list[dict[str, int | str]] | None = None,
    daily_history: list[dict[str, object]] | None = None,
) -> ProjectStats:
    from app.services import daily_learning, learning_insights

    raw = project_items_repo.stats_from_items(items, timezone_name=timezone_name)
    if daily_history is None:
        daily_history = daily_learning.build_daily_history(
            items,
            timezone_name=timezone_name,
            daily_goal=daily_learning.resolve_daily_goal(project),
            active_since=project.created_at,
            daily_goal_history=daily_goal_history,
        )
    enriched = learning_insights.enrich_learning_stats(
        raw,
        project=project,
        items=items,
        timezone_name=timezone_name,
        daily_history=daily_history,
    )
    return ProjectStats.model_validate(enriched)


async def _resolve_daily_goal_history(
    session: AsyncSession,
    project: Project,
    items: list[ProjectItem],
    *,
    timezone_name: str,
    persist: bool = False,
) -> list[dict[str, int | str]]:
    """Compute goal history for stats. Persist only when explicitly requested (not on GET)."""
    from app.services import daily_learning

    history = daily_learning.ensure_daily_goal_history(
        project,
        items,
        timezone_name=timezone_name,
    )
    if not persist:
        return history
    existing = daily_learning.parse_daily_goal_history(project)
    should_persist = project.daily_goal_history is None or (
        len(existing) == 1 and history != existing
    )
    if should_persist and is_learning_product_kind(project.kind):
        await projects_repo.update(session, project, daily_goal_history=history)
    return history


async def list_projects_for_user(
    session: AsyncSession,
    user: User,
    *,
    client_timezone: str | None = None,
) -> list[dict[str, Any]]:
    """Return product learning projects (language + trivia) with optional stats."""
    from app.services import time_context as time_context_service

    items = await projects_repo.list_for_user(session, user.id)
    visible = [item for item in items if is_learning_product_kind(item.kind)]
    learning_ids = [item.id for item in visible]
    stats_by_project: dict[UUID, ProjectStats] = {}
    if learning_ids:
        tz_name = time_context_service.effective_timezone(user.timezone, client_timezone)
        raw_stats = await project_items_repo.count_stats_by_project(
            session,
            learning_ids,
            timezone_by_project={pid: tz_name for pid in learning_ids},
        )
        stats_by_project = {
            pid: ProjectStats.model_validate(raw_stats.get(pid, {})) for pid in learning_ids
        }
    return [
        {
            **{
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "kind": normalize_project_kind(item.kind),
                "target_language": item.target_language,
                "native_language": item.native_language,
                "level": item.level,
                "daily_goal": item.daily_goal,
                "archived": item.archived,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            },
            "stats": stats_by_project.get(item.id),
        }
        for item in visible
    ]


async def create_learning_project(
    session: AsyncSession,
    user: User,
    *,
    title: str,
    description: str | None,
    kind: str,
    target_language: str = "en",
    native_language: str | None = None,
    level: str = "level1",
    daily_goal: int | None = None,
) -> Project:
    """Create a language or trivia project; raises ValueError with a stable code."""
    from app.services import time_context as time_context_service

    normalized = normalize_project_kind(kind)
    if normalized not in LEARNING_PRODUCT_KINDS:
        raise ValueError("unsupported_project_kind")
    if normalized == "language":
        existing = await projects_repo.find_language_by_target(session, user.id, target_language)
        if existing:
            raise ValueError("language_project_exists")
    if normalized == "trivia":
        existing = await projects_repo.find_trivia_project(session, user.id)
        if existing:
            raise ValueError("trivia_project_exists")
    return await projects_repo.create(
        session,
        user_id=user.id,
        title=title,
        description=description,
        kind=normalized,
        target_language=target_language,
        native_language=native_language,
        level=level,
        daily_goal=daily_goal if normalized in LEARNING_PRODUCT_KINDS else None,
        timezone_name=time_context_service.effective_timezone(user.timezone, None),
    )


async def get_project_detail(
    session: AsyncSession,
    user: User,
    project_id: UUID,
    *,
    client_timezone: str | None = None,
    include_lists: bool = False,
) -> dict[str, Any] | None:
    """Assemble project detail for language/trivia; None if missing or unsupported.

    Default response is slim: stats + 14-day count history only. Day item payloads are
    loaded on demand via ``GET /projects/{id}/daily-items``. Pass ``include_lists=True``
    for PDF export (full deck lists).
    """
    from app.models.schemas import ProjectDailyHistoryDay, ProjectOut
    from app.services import daily_learning
    from app.services import time_context as time_context_service

    item = await projects_repo.get_by_id(session, project_id, user.id)
    if item is None or not is_learning_product_kind(item.kind):
        return None

    tz_name = time_context_service.effective_timezone(user.timezone, client_timezone)
    project_items = await project_items_repo.list_for_user(
        session, user.id, project_id=project_id, limit=5000
    )
    # Read path must not write — compute history in memory only.
    goal_history = await _resolve_daily_goal_history(
        session, item, project_items, timezone_name=tz_name, persist=False
    )
    history_rows = daily_learning.build_daily_history(
        project_items,
        timezone_name=tz_name,
        daily_goal=daily_learning.resolve_daily_goal(item),
        active_since=item.created_at,
        daily_goal_history=goal_history,
        days=14,
    )
    stats = _build_enriched_stats(
        item,
        project_items,
        timezone_name=tz_name,
        daily_goal_history=goal_history,
        daily_history=history_rows,
    )
    daily_history = [ProjectDailyHistoryDay.model_validate(row) for row in history_rows]
    lists: list[Any] = []
    if include_lists:
        lists = (
            group_trivia_items(project_items)
            if _is_trivia_project(item)
            else group_items(project_items)
        )
    return {
        **ProjectOut.model_validate(item).model_dump(),
        "kind": normalize_project_kind(item.kind),
        "mastered_count": stats.mastered_count,
        "total_count": stats.total,
        "stats": stats,
        "daily_history": daily_history,
        # Day item maps omitted — client loads via /daily-items for the selected day.
        "daily_items_by_date": {},
        "daily_missed_by_date": {},
        "lists": lists,
    }


async def apply_project_actions(
    session: AsyncSession,
    *,
    user_id: UUID,
    actions: list[ProjectActionItem],
    chat_id: UUID | None = None,
) -> int:
    if not actions:
        return 0
    projects = await projects_repo.list_for_user(session, user_id, limit=200)
    items = await project_items_repo.list_for_user(session, user_id, limit=500)
    applied = 0
    for action in actions:
        title = action.project_title.strip()
        if not title:
            continue
        applied_before = applied
        try:
            if action.action == "create_project":
                kind = normalize_project_kind(action.kind or "language")
                if kind not in LEARNING_PRODUCT_KINDS:
                    continue
                if kind == "language" and _find_language_project(projects, "en"):
                    continue
                if kind == "trivia" and any(_is_trivia_project(p) for p in projects):
                    continue
                if _find_project(projects, title):
                    continue
                project = await projects_repo.create(
                    session,
                    user_id=user_id,
                    title=title,
                    description=(action.description or "").strip() or None,
                    kind=kind,
                    level=action.level or "level1",
                    target_language="en",
                )
                applied += 1
                projects = await projects_repo.list_for_user(session, user_id, limit=200)
                if action.content.strip():
                    list_title = action.list_title.strip() or DEFAULT_LIST
                    await project_items_repo.create(
                        session,
                        user_id=user_id,
                        project_id=project.id,
                        content=action.content,
                        list_title=list_title,
                        note=action.note,
                        definition=action.definition,
                        example_sentence=action.example_sentence or action.note,
                        chat_id=chat_id,
                    )
                    applied += 1
                    items = await project_items_repo.list_for_user(session, user_id, limit=500)
            elif action.action == "delete_project":
                matched = _find_project(projects, title)
                if matched:
                    await projects_repo.delete_by_id(session, matched.id, user_id)
                    applied += 1
                    projects = [p for p in projects if p.id != matched.id]
                    items = [i for i in items if i.project_id != matched.id]
            elif action.action == "set_description":
                matched = _find_project(projects, title)
                if matched:
                    desc = (action.description or "").strip() or None
                    await projects_repo.update(session, matched, description=desc)
                    applied += 1
            elif action.action == "set_level":
                matched = _find_project(projects, title)
                if matched and action.level:
                    await projects_repo.update(session, matched, level=action.level)
                    applied += 1
            else:
                matched = _find_project(projects, title)
                if not matched:
                    continue
                project = matched
                list_title = _resolve_list_title(project, action)
                if action.action == "add":
                    content = action.content.strip()
                    if not content:
                        continue
                    if _find_item(items, project.id, list_title, content):
                        continue
                    await project_items_repo.create(
                        session,
                        user_id=user_id,
                        project_id=project.id,
                        content=content,
                        list_title=list_title,
                        note=action.note,
                        definition=action.definition,
                        example_sentence=action.example_sentence or action.note,
                        chat_id=chat_id,
                        status="new",
                    )
                    applied += 1
                    items = await project_items_repo.list_for_user(session, user_id, limit=500)
                elif action.action == "start_learning":
                    item = _find_item(items, project.id, list_title, action.content)
                    if item and _item_status(item) == "new":
                        await project_items_repo.update(session, item, status="learning")
                        applied += 1
                elif action.action == "master":
                    item = _find_item(
                        items, project.id, list_title, action.content, mastered_only=False
                    )
                    if not item:
                        item = _find_item_by_content(items, project.id, action.content)
                    if item and _item_status(item) != "mastered":
                        if _recently_missed_quiz(item):
                            logger.info(
                                "Skipping master for recently missed quiz item user_id=%s word=%s",
                                user_id,
                                action.content,
                            )
                            continue
                        await project_items_repo.update(session, item, status="mastered")
                        applied += 1
                elif action.action == "unmaster":
                    item = _find_item(
                        items, project.id, list_title, action.content, mastered_only=True
                    )
                    if item and _item_status(item) == "mastered":
                        await project_items_repo.update(session, item, status="learning")
                        applied += 1
                elif action.action == "delete":
                    item = _find_item(items, project.id, list_title, action.content)
                    if item:
                        await project_items_repo.delete_by_id(session, item.id, user_id)
                        applied += 1
                        items = [i for i in items if i.id != item.id]
                elif action.action == "delete_list":
                    removed = await project_items_repo.delete_by_list(
                        session, user_id, project.id, list_title
                    )
                    if removed:
                        applied += 1
                        items = [
                            i
                            for i in items
                            if not (
                                i.project_id == project.id
                                and _list_key(i.list_title) == _list_key(list_title)
                            )
                        ]
        except Exception:
            logger.exception(
                "Failed project action %s for user_id=%s project=%s",
                action.action,
                user_id,
                title,
            )
            continue
        if applied > applied_before:
            logger.info(
                "Project action applied: user_id=%s action=%s project=%s chat_id=%s",
                user_id,
                action.action,
                title,
                chat_id,
            )
    if applied > 0:
        await _invalidate_home_for_user(user_id)
    return applied


@dataclass(frozen=True)
class _ProjectSyncSnapshot:
    snapshot: dict[str, Any]


async def _load_project_sync_snapshot(
    session: AsyncSession,
    user_id: UUID,
    settings: Settings,
) -> _ProjectSyncSnapshot:
    projects = await projects_repo.list_for_user(
        session, user_id, limit=settings.project_inject_limit
    )
    items = await project_items_repo.list_for_user(
        session, user_id, limit=settings.project_item_inject_limit
    )
    return _ProjectSyncSnapshot(
        snapshot={
            "projects": [
                {
                    "title": p.title,
                    "kind": p.kind,
                    "level": getattr(p, "level", "level1"),
                    "target_language": getattr(p, "target_language", "en"),
                    "description": p.description,
                    "archived": p.archived,
                }
                for p in projects
            ],
            "items": [
                {
                    "project_title": next(
                        (pr.title for pr in projects if pr.id == i.project_id), ""
                    ),
                    "list_title": i.list_title,
                    "content": i.content,
                    "definition": i.definition,
                    "example_sentence": i.example_sentence or i.note,
                    "status": _item_status(i),
                    "mastered": i.mastered,
                }
                for i in items
            ],
        }
    )


async def _apply_project_extraction_result(
    session: AsyncSession,
    *,
    user_id: UUID,
    chat_id: UUID,
    result: ProjectExtractionResult | None,
) -> int:
    if not result or not result.actions:
        return 0
    safe_actions: list[ProjectActionItem] = []
    for action in result.actions:
        if action.action in PROJECT_BLOCKED_FROM_TRANSCRIPT:
            logger.warning(
                "Refused destructive project action %s from transcript for "
                "user_id=%s project=%s (requires explicit user action)",
                action.action,
                user_id,
                action.project_title,
            )
            continue
        safe_actions.append(action)
        if len(safe_actions) >= MAX_PROJECT_ACTIONS_PER_TURN:
            break
    if not safe_actions:
        return 0
    applied = await apply_project_actions(
        session,
        user_id=user_id,
        actions=safe_actions,
        chat_id=chat_id,
    )
    if result.actions and applied == 0:
        logger.warning(
            "Project sync extracted %d action(s) but applied 0 for user_id=%s",
            len(result.actions),
            user_id,
        )
    return applied


async def _run_extracted_project_actions(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> ProjectExtractionResult | None:
    from app.core.db import SessionLocal
    from app.gateways import litellm_gateway

    async with SessionLocal() as session:
        loaded = await _load_project_sync_snapshot(session, user_id, settings)
        await session.commit()

    try:
        result = await litellm_gateway.extract_project_actions(
            settings,
            transcript,
            loaded.snapshot,
        )
    except Exception:
        logger.exception("Project action extraction failed for user_id=%s", user_id)
        return None

    async with SessionLocal() as session:
        await _apply_project_extraction_result(
            session,
            user_id=user_id,
            chat_id=chat_id,
            result=result,
        )
        await session.commit()
    return result


async def sync_projects_from_transcript(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> ProjectExtractionResult | None:
    try:
        return await _run_extracted_project_actions(
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript=transcript,
        )
    except Exception:
        logger.exception("Project sync failed for user_id=%s", user_id)
        return None
