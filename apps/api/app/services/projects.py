import logging
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Project, ProjectItem
from app.models.schemas import (
    ProjectActionItem,
    ProjectExtractionResult,
    ProjectItemOut,
    ProjectListGroup,
    ProjectPosGroup,
    ProjectStats,
)
from app.repositories import project_items as project_items_repo
from app.repositories.project_items import pos_list_title
from app.repositories import projects as projects_repo

logger = logging.getLogger(__name__)

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
    "level5": (
        "Advanced (C1): sophisticated vocabulary including nuance and formal register."
    ),
    "level6": (
        "Fluent (C2): full range including rare, literary, and technical words when relevant."
    ),
}

LANGUAGE_TUTOR_HINT = (
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
    "2) Present it like a card, then exactly 4 options labeled A–D (plausible wrong answers):\n"
    "   **Word:** <term> [<part of speech>]\n"
    "   What does it mean?\n"
    "   A) ...  B) ...  C) ...  D) ...\n"
    "3) STOP — wait for the user to reply with A, B, C, or D. Do NOT reveal the answer yet.\n"
    "4) After they answer: if correct → congratulate, explain, give an example, "
    "then offer the next question; if wrong → gently correct and encourage.\n"
    "5) One quiz question per message until they answer.\n"
    "6) **Auto-master:** when the user answers correctly, sync MUST mark that word mastered "
    "immediately — the user must NOT ask you to mark it.\n"
    "7) Keep tone encouraging.\n\n"
    "Encourage progress — mention stats and suggest adding more words appropriate for their level.\n"
    "Status — new = just added; learning = studying; mastered = knows it.\n"
    "Use start_learning when they begin studying a new word; master on every correct quiz answer."
)

PROGRAMMING_TUTOR_HINT = (
    "Active **programming** learning topics — concepts are grouped by journey topic "
    "(Variables, Data types, Functions, …). list_title must match the topic name exactly.\n"
    "When the user learns or demonstrates a concept in chat, emit start_learning or master "
    "with the matching content string from the snapshot.\n"
    "Emit add only for genuinely new concepts. Suggest the topic with the most new/learning "
    "items when they ask what to study next."
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
        "**Word:** apple [noun]\n"
        "A) a red fruit\n"
        "B) a vehicle\n"
        "C) a feeling\n"
        "D) a color\n\n"
        "Do not wrap the word in extra asterisks. Wait for my answer before you explain. "
        "If I'm right, congratulate me, give an example, and mark the word mastered automatically. "
        "If wrong, explain and encourage me. Then ask the next question. "
        "Begin with the first question now."
    )


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


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _list_key(list_title: str) -> str:
    return _normalize(list_title or DEFAULT_LIST)


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
        i
        for i in items
        if i.project_id == project_id and _list_key(i.list_title) == list_norm
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
        skill_line = ""
        if _is_language_project(project):
            skill_line = f"English skill: {guidance}\n"
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
        block = f"{block}\n\n{LANGUAGE_TUTOR_HINT}" if block else LANGUAGE_TUTOR_HINT
    if _is_programming_project(project):
        block = f"{block}\n\n{PROGRAMMING_TUTOR_HINT}" if block else PROGRAMMING_TUTOR_HINT
    if block:
        block = (
            "This chat is linked to ONE learning topic — focus on it unless the user "
            f"explicitly asks about something else.\n\n{block}"
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
    return block


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
    return ProjectStats(**raw)


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
        try:
            if action.action == "create_project":
                if _find_project(projects, title):
                    continue
                kind = action.kind or "general"
                if kind == "vocabulary":
                    kind = "language"
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
                "project_title": next(
                    (pr.title for pr in projects if pr.id == i.project_id), ""
                ),
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
        applied = await apply_project_actions(
            session,
            user_id=user_id,
            actions=result.actions,
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
