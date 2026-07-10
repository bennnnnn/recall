import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
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

_PROJECT_SYNC_TRANSCRIPT = re.compile(
    r"\b("
    r"learning topic|vocab(?:ulary)?|add(?:ed)? (?:word|words)|"
    r"master(?:ed)?|quiz|flashcard|"
    r"set_level|programming (?:topic|project)|"
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
    "The user keeps **learning topics** (shown in the app as **Learning** — study workspaces for "
    "languages, vocab, courses, math, programming concepts, etc.).\n"
    "**Coding repos / software products** (apps to build, 'create my dating app', GitHub projects): "
    "NOT supported yet — those will link via **GitHub** later with dont-do rules per repo. "
    "Do NOT create a learning topic when the user wants to build or manage a codebase. Say coding "
    "projects are coming via GitHub; help in chat or offer a learning topic only if they want to "
    "study concepts or vocab for a stack.\n"
    "When they ask about learning topics, answer from the injected list below.\n"
    "Creating a learning topic via chat — name → type → description → confirm (syncs after reply).\n"
    "For **language/vocabulary**, each user has at most ONE project per language (e.g. one English "
    "vocabulary workspace). Do NOT create a second English project — use set_level on the existing "
    "one when their skill grows.\n"
    "When telling the user their English level, use the plain label only (Beginner, Elementary, "
    "Intermediate, …) — do not mention CEFR or A1–C2 codes unless they ask.\n"
    "For programming learning topics, target_language stores the stack (python, javascript, …).\n"
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
    "'what does it mean?' without A–D choices. Do NOT use teach-then-define-then-quiz.\n"
    "Every question MUST include a readable A–D list AND a ```vocab_quiz JSON fence with the "
    "correct letter (required for the app's tap-to-answer chips and grading):\n"
    f"{VOCAB_QUIZ_FORMAT_BLOCK}\n"
    "Wait for their letter before revealing the answer.\n"
    "**On wrong answers:** say wrong clearly, give the correct meaning briefly, do NOT say "
    "'word mastered', then ask the NEXT word as a fresh multiple-choice question (same format). "
    "Do not re-ask the same MCQ without a new ```vocab_quiz fence.\n"
    "**On correct answers:** congratulate briefly, sync master immediately, then ask the next "
    "word until today's daily_goal is met.\n"
    "Gibberish / unrelated text / random letters other than A–D = wrong.\n"
    "Keep replies short. Prefer new or learning words — never re-quiz ✓ mastered as a 'freebie'.\n"
    "Use the **Today:** line in the project snapshot as the only progress counter.\n\n"
    f"{DAILY_GOAL_COMPLETE_BEHAVIOR}"
)

# Default — chat-based daily sessions (LLM picks format each turn).
LANGUAGE_TUTOR_HINT = LANGUAGE_CHAT_TUTOR_HINT

PROGRAMMING_TUTOR_HINT = (
    "Active **programming** learning — fixed chapters, each with sub-topics (see snapshot). "
    "list_title = chapter title; content = sub-topic text exactly as stored.\n"
    "Teach using the project's stack (target_language = python, javascript, …). "
    "Mark individual sub-topics with start_learning while studying and master when the user "
    "demonstrates each one. A chapter is done only when all its sub-topics are mastered.\n"
    "Work chapters in order; suggest the first chapter that still has new/learning sub-topics."
)

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
    "Do NOT use open-ended or teach-then-check during the daily session — those formats are "
    "unreliable for grading. Wait for A–D before revealing the answer.\n"
    "**On wrong answers:** say wrong clearly, explain briefly, do NOT mark mastered, then ask "
    "the NEXT question in the same ```vocab_quiz format.\n"
    "**On correct answers:** congratulate briefly, sync the fact as mastered, then continue.\n"
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
        "Quiz me in chat — one word at a time. You choose the format each turn."
    )


def _format_missed_quiz_lines(items: list[ProjectItem], *, limit: int = 30) -> list[str]:
    learning = [item for item in items if _item_status(item) == "learning"]
    if not learning:
        return []
    lines = ["\nItems the user missed (prioritize revisiting until mastered):"]
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


async def load_project_quiz_context(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    settings: Settings,
) -> str:
    """Lightweight tutor slice for quiz answer turns — level, pool, and card format."""
    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None:
        return ""
    if _is_trivia_project(project):
        items = await project_items_repo.list_for_user(
            session,
            user_id,
            project_id=project_id,
            limit=settings.project_item_inject_limit,
        )
        lines = [
            f"Active trivia quiz — project: {project.title}.",
            f"Daily goal: {_trivia_daily_goal(project)} correct answers per session.",
            "After feedback, ask the NEXT question using this format:",
            f"{TRIVIA_QUIZ_FENCE_EXAMPLE}",
            "Correct answers are saved automatically — congratulate, explain briefly, continue.",
        ]
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
    quiz_pool = [i for i in items if _item_status(i) in ("new", "learning")]
    level = project.level or "level1"
    lines = [
        f"Active vocabulary quiz — project: {project.title} ({_LEVEL_LABELS.get(level, level)}).",
        f"English skill: {_level_guidance(level)}",
        "After feedback, ask the NEXT question using the same card format:",
        VOCAB_QUIZ_FORMAT_BLOCK,
        "Pick the next word only from new/learning items at this level.",
        "On correct answers, sync MUST master the quizzed word immediately.",
    ]
    if quiz_pool:
        lines.append("\nNew/learning words available:")
        for item in quiz_pool[:40]:
            lines.append(f"- {item.content}")
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


def _recently_missed_quiz(item: ProjectItem, *, within_seconds: int = 180) -> bool:
    missed = getattr(item, "last_incorrect_at", None)
    if not isinstance(missed, datetime):
        return False
    return (datetime.now(UTC) - missed.astimezone(UTC)).total_seconds() < within_seconds


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
) -> QuizAnswerGrade | None:
    """Persist quiz results without waiting on background LLM project sync."""
    from app.services import vocab_quiz as vocab_quiz_service

    quiz = vocab_quiz_service.parse_vocab_quiz(assistant_content)
    letter = vocab_quiz_service.quiz_answer_letter(user_answer)
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

    items = await project_items_repo.list_for_user(
        session, user_id, project_id=project.id, limit=500
    )

    if is_trivia:
        topic = quiz.word.strip()
        question = (quiz.question or quiz.word).strip()
        if not question:
            return None
        list_title = topic or DEFAULT_LIST
        existing = _find_item(items, project.id, list_title, question)
        if existing:
            await project_items_repo.apply_quiz_result(session, existing, is_correct=is_correct)
        else:
            item = await project_items_repo.create(
                session,
                user_id=user_id,
                project_id=project.id,
                content=question,
                list_title=list_title,
                chat_id=chat_id,
                status="new",
            )
            await project_items_repo.apply_quiz_result(session, item, is_correct=is_correct)
        return vocab_quiz_service.QuizAnswerGrade(
            is_correct=is_correct,
            user_letter=letter,
            correct_letter=quiz.correct.upper(),
            word=topic or question[:80],
        )

    if not _is_language_project(project):
        return None

    word = quiz.word.strip()
    if not word:
        return None
    list_title = DEFAULT_LIST
    existing = _find_item(items, project.id, list_title, word) or _find_item_by_content(
        items, project.id, word
    )
    if existing:
        await project_items_repo.apply_quiz_result(session, existing, is_correct=is_correct)
    else:
        item = await project_items_repo.create(
            session,
            user_id=user_id,
            project_id=project.id,
            content=word,
            list_title=list_title,
            chat_id=chat_id,
            status="new",
        )
        await project_items_repo.apply_quiz_result(session, item, is_correct=is_correct)
    return vocab_quiz_service.QuizAnswerGrade(
        is_correct=is_correct,
        user_letter=letter,
        correct_letter=quiz.correct.upper(),
        word=word,
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


def _is_programming_project(project: Project) -> bool:
    return project.kind == "programming"


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
        stack = getattr(project, "target_language", "en") or "en"
        meta = project.kind
        if project.kind == "programming" and stack != "en":
            meta = f"{project.kind}, stack={stack}"
        elif _is_language_project(project):
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
        elif project.kind == "programming" and stack != "en":
            skill_line = f"Programming language: {stack}\n"
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
    remaining = max(0, daily_goal - mastered_today)
    unit = "words mastered" if _is_language_project(project) else "correct"
    if mastered_today >= daily_goal:
        return f"**Today:** {mastered_today}/{daily_goal} {unit} — daily goal complete."
    return (
        f"**Today:** {mastered_today}/{daily_goal} {unit} ({remaining} more needed). "
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
    if _is_programming_project(project):
        block = f"{block}\n\n{PROGRAMMING_TUTOR_HINT}" if block else PROGRAMMING_TUTOR_HINT
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
    if any(_is_programming_project(p) for p in projects):
        block = f"{block}\n\n{PROGRAMMING_TUTOR_HINT}" if block else PROGRAMMING_TUTOR_HINT
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
        if mastered_today >= daily_goal:
            continue
        quiz_label, unit = _daily_learning_quiz_label(project)
        remaining = max(0, daily_goal - mastered_today)
        if total == 0:
            status = f"not started — {remaining} left for today's {quiz_label}"
        elif mastered_today == 0:
            status = f"not started — {remaining} left for today's {quiz_label}"
        else:
            status = f"{remaining} left for today's {quiz_label}"
        lines.append(
            f"- {project.title} ({quiz_label}): {mastered_today}/{daily_goal} {unit} ({status})"
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
                kind = action.kind or "general"
                if kind == "vocabulary":
                    kind = "language"
                if kind == "programming":
                    continue
                if kind == "language" and _find_language_project(projects, "en"):
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
