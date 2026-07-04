import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Project, ProjectItem, User
from app.models.schemas import (
    ProjectActionItem,
    ProjectExtractionResult,
    ProjectItemOut,
    ProjectListGroup,
    ProjectPosGroup,
    ProjectStats,
)
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.repositories.project_items import pos_list_title

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
POS_ORDER = (
    "noun",
    "verb",
    "adjective",
    "adverb",
    "pronoun",
    "preposition",
    "conjunction",
    "interjection",
    "phrase",
    "other",
)

_PROJECT_SYNC_TRANSCRIPT = re.compile(
    r"\b("
    r"learning topic|vocab(?:ulary)?|add(?:ed)? (?:word|words)|"
    r"master(?:ed)?|quiz|flashcard|"
    r"set_level|programming (?:topic|project)|"
    r"noun|verb|adjective|part of speech|"
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
    "For programming learning topics, target_language stores the stack (python, javascript, …).\n"
    "Do not invent titles or list names the user did not choose."
)

LEVEL_GUIDANCE: dict[str, str] = {
    "level1": (
        "Beginner (CEFR A1): only basic high-frequency words — cat, eat, book, go, hello, water. "
        "Never quiz or add advanced/rare words (ubiquitous, pragmatic, ephemeral, mitigate)."
    ),
    "level2": (
        "Elementary (A2): everyday words a new learner meets in simple conversations. "
        "Avoid academic or rare vocabulary."
    ),
    "level3": (
        "Intermediate (B1): common words plus some idioms. Still avoid highly specialized jargon."
    ),
    "level4": (
        "Upper intermediate (B2): broader vocabulary including less common but still useful words."
    ),
    "level5": ("Advanced (C1): sophisticated vocabulary including nuance and formal register."),
    "level6": (
        "Fluent (C2): full range including rare, literary, and technical words when relevant."
    ),
}

VOCAB_QUIZ_MARKDOWN_EXAMPLE = (
    "**Word:** apple [noun]\n"
    "What does it mean?\n"
    "A) a red fruit\n"
    "B) a vehicle\n"
    "C) a feeling\n"
    "D) a color"
)

VOCAB_QUIZ_FENCE_EXAMPLE = (
    "```vocab_quiz\n"
    '{"word":"apple","part_of_speech":"noun","question":"What does it mean?",'
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
    "```vocab_card\n"
    '{"word":"resilient","part_of_speech":"adjective",'
    '"definition":"able to recover quickly from difficulty",'
    '"example_sentence":"She stayed resilient after the setback."}\n'
    "```"
)

VOCAB_CARD_FORMAT_BLOCK = (
    "Present each new word with a short friendly explanation, then append:\n"
    f"{VOCAB_CARD_FENCE_EXAMPLE}\n"
    "The card is for the app UI — keep your prose natural above it."
)

LANGUAGE_EXAM_TUTOR_HINT = (
    "Active **language** projects (English etc.) — you are the user's vocabulary tutor.\n"
    "The project **level** is the user's **English skill level** (level1=beginner … level6=fluent), "
    "NOT word difficulty stored per word.\n"
    "Each word has: term (content), part_of_speech, definition, example_sentence, status "
    "(new | learning | mastered).\n\n"
    "**Grouping — mandatory:**\n"
    "Every word MUST have part_of_speech. Words are stored in separate groups by speech type "
    "(nouns, verbs, adjectives, …). Never mix nouns and verbs in one group. "
    "book→noun/nouns, eat→verb/verbs.\n"
    "When adding via sync, always set part_of_speech; list_title becomes nouns/verbs automatically.\n\n"
    "**Level rules — mandatory:**\n"
    "Match ALL quiz words and suggested new words to the project's level:\n"
    + "\n".join(f"- {k}: {v}" for k, v in LEVEL_GUIDANCE.items())
    + "\n\n"
    "**Interactive quiz (in chat — primary way to practice):**\n"
    "The user quizzes WITH you, not alone. Run a turn-by-turn multiple-choice quiz:\n"
    "1) Pick ONE word from their new/learning items that fits their project level "
    "(for level1, only the simplest words in their list).\n"
    "2) Present the quiz card using this EXACT format every time:\n"
    f"{VOCAB_QUIZ_FORMAT_BLOCK}\n"
    "3) STOP — wait for the user to reply with A, B, C, or D. Do NOT reveal the answer yet.\n"
    "4) After they answer: if correct → congratulate, explain, give an example, "
    "then ask the next question; if wrong → gently correct and encourage.\n"
    "5) One quiz question per message until they answer.\n"
    "6) **Auto-master:** when the user answers correctly, sync MUST mark that word mastered "
    "immediately — the user must NOT ask you to mark it.\n"
    "7) Keep tone encouraging.\n\n"
    "Use start_learning when they begin studying a new word; master on every correct quiz answer.\n\n"
    "**Daily vocabulary batches (primary learning mode):**\n"
    "Each project has daily_goal = N words per session (shown in the snapshot).\n"
    "1) If ANY words are still new or learning, quiz those first — do NOT add new words yet.\n"
    "2) When there are no pending new/learning words (or the user asks for today's words), "
    "add exactly N fresh words at their English level via sync. Never duplicate a term "
    "already in the deck (check content).\n"
    "3) Teach each word briefly, then quiz one at a time until all N are mastered.\n"
    "4) The user's dashboard tracks today's mastered count vs daily_goal and total words "
    "accumulated over time.\n"
    "5) When today's N words are all mastered, congratulate in plain markdown only — "
    "the app tracks completion automatically. NEVER append ```json, session_complete, "
    "words_learned, or any other machine-readable block on completion messages "
    "(only ```vocab_quiz during active quiz questions).\n"
    "6) **Daily goal reached:** When the user has already mastered daily_goal words today, "
    "tell them clearly that today's goal is done. Do NOT sync new words. Only add a bonus "
    "batch if they explicitly ask for extra/more/bonus words beyond today's goal — confirm first."
)

LANGUAGE_CHAT_TUTOR_HINT = (
    "Active **language** project — **chat tutor mode** (conversational learning, NOT multiple choice).\n"
    "The project **level** is the user's **English skill level** (level1=beginner … level6=fluent).\n"
    "Each word has: term, part_of_speech, definition, example_sentence, status "
    "(new | learning | mastered).\n\n"
    "**How to teach (one word per turn):**\n"
    "1) Pick ONE new/learning word at the user's level.\n"
    "2) In plain markdown: show the word, a clear definition, and one example sentence.\n"
    "3) Append the vocab card block for the app UI:\n"
    f"{VOCAB_CARD_FORMAT_BLOCK}\n"
    '4) STOP — invite the user to reply naturally: e.g. "got it", "more examples", '
    '"use it in a sentence", or ask a question. Do NOT ask for A/B/C/D.\n'
    "5) When they show understanding, congratulate briefly and use sync to "
    "start_learning or master the word — never wait for them to ask.\n"
    "6) Then move to the next word until today's daily_goal is met.\n"
    '7) If the user says "quiz me", "test me", or opens exam mode, switch to '
    "multiple-choice vocab_quiz cards (exam rules).\n\n"
    "**Do NOT use ```vocab_quiz in chat tutor mode** unless the user explicitly "
    "requests a quiz question.\n\n"
    "**Daily batches:** Same rules as exam mode for daily_goal — quiz/teach pending "
    "words first; add fresh words only to fill today's goal; stop when goal is met."
)

# Legacy alias — exam-style MC quiz (default when quiz_mode is unset).
LANGUAGE_TUTOR_HINT = LANGUAGE_EXAM_TUTOR_HINT

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

TRIVIA_EXAM_TUTOR_HINT = (
    "Active **trivia** project — **exam quiz mode** (multiple choice).\n"
    "Quiz topics are in project description (comma-separated ids: history, science, …).\n"
    "daily_goal = number of questions to get correct per session.\n"
    "Each saved fact: list_title = topic label (e.g. History), content = short question, "
    "definition = explanation.\n\n"
    "**Daily quiz (in chat — primary mode):**\n"
    "1) Ask ONE multiple-choice question at a time from the user's topics.\n"
    "2) Use vocab_quiz JSON with quiz_type=trivia — word = topic label ONLY (e.g. History), "
    "question = the full question text. NEVER set part_of_speech for trivia.\n"
    f"Example:\n{TRIVIA_QUIZ_FENCE_EXAMPLE}\n"
    "3) STOP — wait for A, B, C, or D before revealing the answer.\n"
    "4) If correct → congratulate, explain — the app saves the fact automatically (no sync needed).\n"
    "5) If wrong → explain gently, then ask the next question.\n"
    "6) Continue until the user has daily_goal correct answers today.\n"
    "7) Do not repeat questions already in the deck. Mix topics across the session.\n"
    "8) When today's goal is met, congratulate clearly — today's quiz is done. "
    "Do NOT ask new questions unless the user explicitly wants bonus questions beyond today's goal.\n"
    "9) Completion messages are markdown only — NEVER append ```json or session metadata "
    "(the app tracks daily progress automatically).\n\n"
    "**Export / PDF:** When the user asks to export, download, print, or save their progress "
    "as a PDF (or report), write a complete structured summary in markdown: title, date, "
    "topics, stats, and a list of mastered facts. Never say you cannot generate PDFs — tell "
    "them to tap the **document export** icon on your message to save a PDF file."
)

TRIVIA_CHAT_TUTOR_HINT = (
    "Active **trivia** project — **chat tutor mode** (conversational, NOT multiple choice).\n"
    "Topics are in project description. daily_goal = correct facts to learn per session.\n\n"
    "**How to teach:** Share one interesting fact or question at a time in plain prose. "
    'Explain the answer when the user engages ("got it", "tell me more", "why?"). '
    "Save mastered facts via background sync when they demonstrate understanding.\n"
    "Do NOT use ```vocab_card or teach English vocabulary words — this is general knowledge, not language.\n"
    "Do NOT use ```vocab_quiz unless the user explicitly asks to be quizzed with A–D.\n"
    "When today's daily_goal is met, congratulate and stop unless they want bonus facts."
)

TRIVIA_TUTOR_HINT = TRIVIA_EXAM_TUTOR_HINT


def _language_tutor_hint(quiz_mode: str | None) -> str:
    if quiz_mode == "chat":
        return LANGUAGE_CHAT_TUTOR_HINT
    return LANGUAGE_EXAM_TUTOR_HINT


def _trivia_tutor_hint(quiz_mode: str | None) -> str:
    if quiz_mode == "chat":
        return TRIVIA_CHAT_TUTOR_HINT
    return TRIVIA_EXAM_TUTOR_HINT


def _quiz_mode_banner(quiz_mode: str | None, *, kind: str | None = None) -> str:
    if quiz_mode == "chat":
        if kind == "trivia":
            return (
                "**Presentation mode: chat tutor.** Share general-knowledge facts in conversational prose. "
                "Do NOT use vocab_card or teach vocabulary words. Multiple-choice only if the user asks."
            )
        return (
            "**Presentation mode: chat tutor.** Teach in conversational prose; "
            "use vocab_card for language words. Multiple-choice only if the user asks."
        )
    if quiz_mode == "exam":
        return (
            "**Presentation mode: exam quiz.** One multiple-choice question per turn "
            "using vocab_quiz JSON; wait for A–D before explaining."
        )
    return (
        "**Presentation mode: exam quiz (default).** One multiple-choice question per turn "
        "using vocab_quiz JSON; wait for A–D before explaining."
    )


def _level_guidance(level: str) -> str:
    return LEVEL_GUIDANCE.get(level or "level1", LEVEL_GUIDANCE["level1"])


_LEVEL_LABELS: dict[str, str] = {
    "level1": "Beginner (A1)",
    "level2": "Elementary (A2)",
    "level3": "Intermediate (B1)",
    "level4": "Upper intermediate (B2)",
    "level5": "Advanced (C1)",
    "level6": "Fluent (C2)",
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
    lvl = _LEVEL_LABELS.get(project.level or "level1", "Beginner (A1)")
    goal = (
        f" {project.description.strip()}."
        if project.description and project.description.strip()
        else ""
    )
    return (
        f'Start an interactive vocabulary quiz for my "{title}" English project.\n'
        f"My English level: {lvl}.{goal}\n"
        f"{_language_progress_line(stats)}\n\n"
        "Quiz me in chat: one word at a time from my new and learning words, matched to my level.\n"
        "Use this EXACT format for every question (required for the quiz card UI):\n\n"
        f"{VOCAB_QUIZ_FORMAT_BLOCK}\n\n"
        "Do not wrap the word in extra asterisks. Wait for my answer before you explain. "
        "If I'm right, congratulate me, give an example, and mark the word mastered automatically. "
        "If wrong, explain and encourage me. Then ask the next question. "
        "Begin with the first question now."
    )


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
        return (
            f"Active trivia quiz — project: {project.title}.\n"
            f"Daily goal: {_trivia_daily_goal(project)} correct answers per session.\n"
            "After feedback, ask the NEXT question using this format:\n"
            f"{TRIVIA_QUIZ_FENCE_EXAMPLE}\n"
            "Correct answers are saved automatically — congratulate, explain briefly, continue."
        )
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
            pos = item.part_of_speech or "other"
            lines.append(f"- {item.content} [{pos}]")
    return "\n".join(lines)


async def _resolve_quiz_project_id(
    session: AsyncSession,
    user_id: UUID,
    *,
    project_id: UUID | None,
    quiz: object,
) -> UUID | None:
    if project_id is not None:
        return project_id
    is_trivia = getattr(quiz, "quiz_type", None) == "trivia" or (
        getattr(quiz, "question", None) is not None
        and getattr(quiz, "part_of_speech", None) is None
        and getattr(quiz, "quiz_type", None) != "vocab"
    )
    if is_trivia:
        project = await projects_repo.find_trivia_project(session, user_id)
        return project.id if project else None
    project = await projects_repo.find_language_by_target(session, user_id, "en")
    return project.id if project else None


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
) -> bool:
    """Persist quiz results without waiting on background LLM project sync."""
    from app.services import vocab_quiz as vocab_quiz_service

    quiz = vocab_quiz_service.parse_vocab_quiz(assistant_content)
    letter = vocab_quiz_service.quiz_answer_letter(user_answer)
    if letter is None:
        return False

    if quiz is None and topic_hint and question_hint:
        from app.services.vocab_quiz import ParsedVocabQuiz

        quiz = ParsedVocabQuiz(
            word=topic_hint.strip(),
            part_of_speech=None,
            question=question_hint.strip(),
            correct=None,
            quiz_type="trivia",
        )
    if quiz is None:
        return False

    resolved_project_id = await _resolve_quiz_project_id(
        session, user_id, project_id=project_id, quiz=quiz
    )
    if resolved_project_id is None:
        return False

    project = await projects_repo.get_by_id(session, resolved_project_id, user_id)
    if project is None:
        return False

    is_trivia = (
        _is_trivia_project(project)
        or quiz.quiz_type == "trivia"
        or (quiz.question is not None and not quiz.part_of_speech)
    )
    is_correct: bool | None = None
    if quiz.correct:
        is_correct = letter == quiz.correct.upper()
    elif is_correct_hint is not None:
        is_correct = is_correct_hint
    if is_correct is None:
        return False

    items = await project_items_repo.list_for_user(
        session, user_id, project_id=resolved_project_id, limit=500
    )

    if is_trivia:
        topic = quiz.word.strip()
        question = (quiz.question or quiz.word).strip()
        if not question:
            return False
        list_title = topic or DEFAULT_LIST
        status = "mastered" if is_correct else "learning"
        existing = _find_item(items, project.id, list_title, question)
        if existing:
            if _item_status(existing) != status:
                await project_items_repo.update(session, existing, status=status)
        else:
            await project_items_repo.create(
                session,
                user_id=user_id,
                project_id=project.id,
                content=question,
                list_title=list_title,
                chat_id=chat_id,
                status=status,
            )
        return True

    if not _is_language_project(project) or not is_correct:
        return False

    word = quiz.word.strip()
    if not word:
        return False
    pos = (quiz.part_of_speech or "other").strip().lower()
    list_title = pos_list_title(pos)
    existing = _find_item(items, project.id, list_title, word) or _find_item_by_content(
        items, project.id, word
    )
    if existing:
        if _item_status(existing) != "mastered":
            await project_items_repo.update(session, existing, status="mastered")
    else:
        await project_items_repo.create(
            session,
            user_id=user_id,
            project_id=project.id,
            content=word,
            list_title=list_title,
            part_of_speech=pos,
            chat_id=chat_id,
            status="mastered",
        )
    return True


async def record_project_quiz_answer(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    chat_id: UUID,
    assistant_message_id: UUID,
    letter: str,
    topic: str | None = None,
    question: str | None = None,
    is_correct: bool | None = None,
) -> bool:
    from app.repositories import chats as chats_repo
    from app.repositories import messages as messages_repo

    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None:
        return False
    chat = await chats_repo.get_by_id(session, chat_id, user_id)
    if chat is None:
        return False
    message = await messages_repo.get_by_id(session, assistant_message_id, chat_id)
    if message is None or message.role != "assistant":
        return False

    recorded = await apply_deterministic_quiz_answer(
        session,
        user_id=user_id,
        chat_id=chat_id,
        project_id=project_id,
        assistant_content=message.content,
        user_answer=letter,
        topic_hint=topic,
        question_hint=question,
        is_correct_hint=is_correct,
    )
    if recorded and chat.project_id is None:
        await chats_repo.set_project_id(session, chat, project_id)
    if recorded:
        await _invalidate_home_for_user(user_id)
    return recorded


def _resolve_list_title(project: Project, action: ProjectActionItem) -> str:
    if _is_language_project(project):
        pos = (action.part_of_speech or "").strip().lower() or "other"
        return pos_list_title(pos)
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


def _find_programming_project(
    projects: list[Project],
    target_language: str,
) -> Project | None:
    lang = (target_language or "").strip().lower()
    if not lang:
        return None
    for project in projects:
        if (
            _is_programming_project(project)
            and (project.target_language or "").strip().lower() == lang
        ):
            return project
    return None


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
        if _is_language_project(project):
            by_pos: dict[str, list[ProjectItem]] = {}
            for item in project_items:
                pos = (item.part_of_speech or "other").lower()
                by_pos.setdefault(pos, []).append(item)
            for pos in POS_ORDER:
                if pos not in by_pos:
                    continue
                lines.append(f"\n#### {pos.title()}s")
                for item in by_pos[pos]:
                    lines.append(_format_vocab_line(item))
            for pos, pos_items in by_pos.items():
                if pos in POS_ORDER:
                    continue
                lines.append(f"\n#### {pos.title()}")
                for item in pos_items:
                    lines.append(_format_vocab_line(item))
            continue
        by_list: dict[str, list[ProjectItem]] = {}
        for item in project_items:
            lst = item.list_title.strip() or DEFAULT_LIST
            by_list.setdefault(lst, []).append(item)
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
    pos = f" [{item.part_of_speech}]" if item.part_of_speech else ""
    defn = f" — {item.definition}" if item.definition else ""
    example = item.example_sentence or item.note
    ex = f' e.g. "{example}"' if example else ""
    return f"- {mark} {item.content}{pos}{defn}{ex} ({status})"


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


async def load_project_for_prompt(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    settings: Settings,
    *,
    quiz_mode: str | None = None,
) -> str:
    project = await projects_repo.get_by_id(session, project_id, user_id)
    if project is None:
        return ""
    items = await project_items_repo.list_for_user(
        session,
        user_id,
        project_id=project_id,
        limit=settings.project_item_inject_limit,
    )
    block = format_projects_block([project], items)
    if _is_language_project(project):
        hint = _language_tutor_hint(quiz_mode)
        block = f"{block}\n\n{hint}" if block else hint
    if _is_programming_project(project):
        block = f"{block}\n\n{PROGRAMMING_TUTOR_HINT}" if block else PROGRAMMING_TUTOR_HINT
    if _is_trivia_project(project):
        hint = _trivia_tutor_hint(quiz_mode)
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


async def load_daily_learning_summary_for_prompt(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    client_timezone: str | None = None,
) -> str:
    """Compact today-only stats for end-of-day reflection (not full word lists)."""
    from app.services import daily_learning
    from app.services import time_context as time_context_service

    projects = await projects_repo.list_for_user(
        session, user.id, limit=settings.project_inject_limit
    )
    tz_name = time_context_service.effective_timezone(user.timezone, client_timezone)
    lines: list[str] = []
    for project in projects:
        if not (_is_language_project(project) or _is_trivia_project(project)):
            continue
        stats = await project_items_repo.count_stats(
            session,
            project.id,
            user.id,
            timezone_name=tz_name,
        )
        daily_goal = daily_learning.resolve_daily_goal(project)
        mastered_today = int(stats.get("mastered_today") or 0)
        pending_today = int(stats.get("pending_today") or 0)
        if mastered_today == 0 and pending_today == 0:
            continue
        if _is_language_project(project):
            unit = "words mastered today"
        else:
            unit = "correct today"
        if mastered_today >= daily_goal:
            status = "daily goal complete"
        else:
            remaining = max(0, daily_goal - mastered_today)
            status = f"{remaining} left for today's goal"
        lines.append(f"- {project.title}: {mastered_today}/{daily_goal} {unit} ({status})")
    if not lines:
        return ""
    return "Today's learning progress:\n" + "\n".join(lines)


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


def group_programming_items(items: list[ProjectItem]) -> list[ProjectListGroup]:
    from app.services.programming_curriculum import CURRICULUM_TOPIC_ORDER

    by_list: dict[str, list[ProjectItem]] = {}
    for item in items:
        lst = item.list_title.strip() or DEFAULT_LIST
        by_list.setdefault(lst, []).append(item)
    order = {name: idx for idx, name in enumerate(CURRICULUM_TOPIC_ORDER)}

    def topic_sort_key(title: str) -> tuple[int, str]:
        return (order.get(title, len(CURRICULUM_TOPIC_ORDER)), title.casefold())

    groups: list[ProjectListGroup] = []
    for list_title in sorted(by_list.keys(), key=topic_sort_key):
        topic_items = sorted(by_list[list_title], key=lambda i: i.content.casefold())
        groups.append(
            ProjectListGroup(
                list_title=list_title,
                items=[ProjectItemOut.model_validate(i) for i in topic_items],
            )
        )
    return groups


def group_by_part_of_speech(items: list[ProjectItem]) -> list[ProjectPosGroup]:
    by_pos: dict[str, list[ProjectItem]] = {}
    for item in items:
        pos = (item.part_of_speech or "other").lower()
        by_pos.setdefault(pos, []).append(item)

    def sort_key(pos: str) -> tuple[int, str]:
        try:
            return (POS_ORDER.index(pos), pos)
        except ValueError:
            return (len(POS_ORDER), pos)

    groups: list[ProjectPosGroup] = []
    for pos in sorted(by_pos.keys(), key=sort_key):
        groups.append(
            ProjectPosGroup(
                part_of_speech=pos,
                items=[ProjectItemOut.model_validate(i) for i in by_pos[pos]],
            )
        )
    return groups


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
                if kind == "language" and _find_language_project(projects, "en"):
                    continue
                stack = "python" if kind == "programming" else "en"
                if kind == "programming" and _find_programming_project(projects, stack):
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
                    target_language=stack,
                )
                applied += 1
                if _is_programming_project(project):
                    from app.services.programming_curriculum import seed_programming_curriculum

                    await seed_programming_curriculum(
                        session, user_id=user_id, project_id=project.id
                    )
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
                        part_of_speech=action.part_of_speech,
                        chat_id=chat_id,
                    )
                    applied += 1
                    items = await project_items_repo.list_for_user(session, user_id, limit=500)
            elif action.action == "delete_project":
                project = _find_project(projects, title)
                if project:
                    await projects_repo.delete_by_id(session, project.id, user_id)
                    applied += 1
                    projects = [p for p in projects if p.id != project.id]
                    items = [i for i in items if i.project_id != project.id]
            elif action.action == "set_description":
                project = _find_project(projects, title)
                if project:
                    desc = (action.description or "").strip() or None
                    await projects_repo.update(session, project, description=desc)
                    applied += 1
            elif action.action == "set_level":
                project = _find_project(projects, title)
                if project and action.level:
                    await projects_repo.update(session, project, level=action.level)
                    applied += 1
            else:
                project = _find_project(projects, title)
                if not project:
                    continue
                list_title = _resolve_list_title(project, action)
                if action.action == "add":
                    content = action.content.strip()
                    if not content:
                        continue
                    pos = (action.part_of_speech or "").strip().lower()
                    if _is_language_project(project) and not pos:
                        pos = "other"
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
                        part_of_speech=pos or action.part_of_speech,
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


async def sync_projects_from_transcript(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> ProjectExtractionResult | None:
    from app.gateways import litellm_gateway

    projects = await projects_repo.list_for_user(
        session, user_id, limit=settings.project_inject_limit
    )
    items = await project_items_repo.list_for_user(
        session, user_id, limit=settings.project_item_inject_limit
    )
    snapshot = {
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
                "project_title": next((pr.title for pr in projects if pr.id == i.project_id), ""),
                "list_title": i.list_title,
                "content": i.content,
                "part_of_speech": i.part_of_speech,
                "definition": i.definition,
                "example_sentence": i.example_sentence or i.note,
                "status": _item_status(i),
                "mastered": i.mastered,
            }
            for i in items
        ],
    }
    try:
        result = await litellm_gateway.extract_project_actions(
            settings,
            transcript,
            snapshot,
        )
        if not result or not result.actions:
            return result
        # Defensive: cap actions per turn and refuse whole-project / whole-deck
        # deletes inferred from a transcript. The user must remove those
        # explicitly from the Projects screen.
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
            return result
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
        return result
    except Exception:
        logger.exception("Project sync failed for user_id=%s", user_id)
        return None
