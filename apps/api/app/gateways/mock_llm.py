import asyncio
import logging
import re
from collections.abc import AsyncIterator

from app.core.config import Settings
from app.services.chat_titles import normalize_chat_title

logger = logging.getLogger(__name__)

MOCK_REPLY = (
    "I'm Recall (mock mode). Add OPENROUTER_API_KEY in apps/api/.env "
    "to get real responses. Memory, history, and quotas still work end-to-end."
)

MOCK_QUIZ_QUESTION = (
    "**Word:** ubiquitous [noun]\n\n"
    "What does it mean?\n\n"
    "A) Extremely rare and hard to find\n"
    "B) Present or found everywhere\n"
    "C) Related to transportation\n"
    "D) A type of musical instrument\n\n"
    "Tap A, B, C, or D — I'll wait for your answer before revealing it."
)

MOCK_QUIZ_FEEDBACK = (
    "Nice work — **B** is correct! *Ubiquitous* means something is everywhere you look.\n\n"
    'Example: "Smartphones are ubiquitous in modern cities."\n\n'
    "Want another question?"
)


def should_mock_llm(settings: Settings) -> bool:
    has_key = bool(settings.openrouter_api_key)
    return settings.mock_llm_enabled and not has_key


def _last_user_text(messages: list[dict[str, str]] | None) -> str:
    if not messages:
        return ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content") or "").strip()
    return ""


def mock_reply_for_messages(messages: list[dict[str, str]] | None) -> str:
    last_user = _last_user_text(messages)
    lower = last_user.lower()
    if re.match(r"^[a-d]\)?$", lower) or lower in {"a", "b", "c", "d"}:
        return MOCK_QUIZ_FEEDBACK
    if "quiz" in lower or "multiple-choice" in lower or "vocabulary quiz" in lower:
        return MOCK_QUIZ_QUESTION
    return MOCK_REPLY


async def mock_stream(
    text: str | None = None,
    *,
    messages: list[dict[str, str]] | None = None,
) -> AsyncIterator[str]:
    reply = text if text is not None else mock_reply_for_messages(messages)
    for word in reply.split(" "):
        yield word + " "
        await asyncio.sleep(0.03)


async def mock_title(user_message: str) -> str | None:
    words = user_message.strip().split()[:4]
    if not words:
        return None
    return normalize_chat_title(" ".join(words))


async def mock_memory_sections(user_message: str, existing_sections: dict[str, str]):
    from app.models.schemas import MemorySectionItem, MemorySectionUpdateResult

    if len(user_message.strip()) < 10:
        return None
    return MemorySectionUpdateResult(
        sections=[
            MemorySectionItem(
                type="focus",
                summary=f"Recently discussed: {user_message[:400]}",
                confidence=0.6,
            )
        ]
    )


async def mock_memories(user_message: str):
    return await mock_memory_sections(user_message, {})


async def mock_rewrite_memory_sections(sections: dict[str, str]):
    from app.models.schemas import MemorySectionItem, MemorySectionUpdateResult

    if not sections:
        return None
    rewritten: list[MemorySectionItem] = []
    for memory_type, text in sections.items():
        sentences = [part.strip() for part in text.split(".") if part.strip()]
        unique: list[str] = []
        seen: set[str] = set()
        for sentence in sentences:
            key = sentence.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(sentence)
        summary = ". ".join(unique[:3]).strip()
        if summary and not summary.endswith("."):
            summary += "."
        rewritten.append(
            MemorySectionItem(type=memory_type, summary=summary or text[:300], confidence=0.85)
        )
    return MemorySectionUpdateResult(sections=rewritten)


async def mock_todo_actions(user_message: str, current_todos: list[dict[str, object]]):
    from app.models.schemas import TodoActionItem, TodoExtractionResult

    text = user_message.lower()
    actions: list[TodoActionItem] = []
    if "delete" in text and "list" in text:
        topics = {str(t.get("topic") or "") for t in current_todos if t.get("topic")}
        for topic in sorted(topics):
            if topic and topic.lower() in text:
                actions.append(
                    TodoActionItem(action="delete_list", topic=topic, content="")
                )
                break
    if "add" in text or "remind me" in text:
        # crude: extract after "add" or use whole user line
        for line in user_message.splitlines():
            if line.lower().startswith("user:"):
                content = line.split(":", 1)[-1].strip()
                if len(content) > 3:
                    actions.append(TodoActionItem(action="add", topic="General", content=content[:200]))
                    break
    if "done" in text or "complete" in text or "finished" in text:
        open_items = [t for t in current_todos if not t.get("checked")]
        if open_items:
            first = open_items[0]
            actions.append(
                TodoActionItem(
                    action="complete",
                    topic=str(first.get("topic") or "General"),
                    content=str(first["content"]),
                )
            )
    if not actions:
        return None
    return TodoExtractionResult(actions=actions)


def _match_project_title(transcript: str, projects: list[dict[str, object]]) -> str | None:
    text = transcript.lower()
    for proj in projects:
        if not isinstance(proj, dict):
            continue
        title = str(proj.get("title") or "").strip()
        if title and title.lower() in text:
            return title
    if projects and isinstance(projects[0], dict):
        return str(projects[0].get("title") or "").strip() or None
    return None


def _infer_list_title(transcript: str) -> str:
    text = transcript.lower()
    for pattern in (
        r"(?:to|in|on|under)\s+(?:the\s+)?([a-z0-9][a-z0-9\s-]{1,40}?)\s+list",
        r"list[:\s]+([a-z0-9][a-z0-9\s-]{1,40})",
        r"([a-z0-9][a-z0-9\s-]{1,30})\s+group",
    ):
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip(" .,-")
            if name and name not in ("my", "the", "a", "this", "your"):
                return name.title()
    if "travel" in text:
        return "Travel"
    if "food" in text:
        return "Food"
    return "General"


def _extract_vocab_terms(transcript: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        cleaned = term.strip(" .,:;!?\"'()[]")
        key = cleaned.lower()
        if not cleaned or len(cleaned) > 80 or key in seen:
            return
        if cleaned.lower() in {"add", "added", "words", "word", "list", "project", "vocabulary"}:
            return
        seen.add(key)
        terms.append(cleaned)

    # Quoted words: 'hello', "hola"
    for match in re.finditer(r"""['"]([^'"]{1,60})['"]""", transcript):
        add(match.group(1))

    # Assistant-style lists: hello, hola, and gracias
    for line in transcript.splitlines():
        lower = line.lower()
        if not (
            lower.startswith("assistant:")
            or "add" in lower
            or "added" in lower
            or "words" in lower
        ):
            continue
        segment = line.split(":", 1)[-1] if ":" in line else line
        segment = re.sub(
            r"(?i)^.*?(?:add(?:ed|ing)?|include|here are)[:\s-]*",
            "",
            segment,
        )
        for part in re.split(r",|\band\b|\n|;", segment):
            chunk = part.strip(" .")
            if not chunk:
                continue
            # "word (translation)" -> take first token group
            chunk = re.sub(r"\s*[\(\[].*?[\)\]]", "", chunk).strip()
            if re.match(r"^[\w\s-]{1,40}$", chunk, re.UNICODE):
                add(chunk)

    # User: add hello, world, foo
    for line in transcript.splitlines():
        if not line.lower().startswith("user:"):
            continue
        segment = line.split(":", 1)[-1]
        if "add" not in segment.lower():
            continue
        after_add = re.split(r"(?i)\badd(?:\s+\d+\s+\w+)?\s+", segment, maxsplit=1)
        if len(after_add) < 2:
            continue
        tail = after_add[1]
        tail = re.split(r"(?i)\s+(?:to|in|on|under)\s+", tail, maxsplit=1)[0]
        for part in re.split(r",|\band\b", tail):
            chunk = part.strip(" .")
            if re.match(r"^[\w\s-]{1,40}$", chunk, re.UNICODE):
                add(chunk)

    return terms[:20]


def _guess_part_of_speech(term: str) -> str:
    lower = term.strip().lower()
    if lower.endswith("ly") and len(lower) > 3:
        return "adverb"
    if lower.endswith(("ful", "ous", "ive", "al", "ic")) and len(lower) > 4:
        return "adjective"
    verbs = {
        "eat",
        "go",
        "run",
        "walk",
        "see",
        "make",
        "take",
        "come",
        "think",
        "look",
        "want",
        "use",
        "find",
        "give",
        "tell",
        "work",
        "call",
        "try",
        "ask",
        "need",
        "feel",
        "become",
        "leave",
        "put",
        "mean",
        "keep",
        "let",
        "begin",
        "seem",
        "help",
        "talk",
        "turn",
        "start",
        "show",
        "hear",
        "play",
        "move",
        "live",
        "believe",
        "bring",
        "write",
        "sit",
        "stand",
        "learn",
        "read",
    }
    if lower in verbs or lower.endswith("ing"):
        return "verb"
    return "noun"


def _extract_quiz_word(transcript: str) -> str | None:
    matches = re.findall(r"(?:\*\*Word:\*\*|Word:)\s*([^\n\[]+)", transcript, flags=re.I)
    if not matches:
        return None
    return matches[-1].strip()


def _extract_quiz_answer(transcript: str) -> str | None:
    for line in reversed(transcript.splitlines()):
        if not line.lower().startswith("user:"):
            continue
        answer = line.split(":", 1)[-1].strip()
        if re.match(r"^[A-Da-d]\)?$", answer):
            return answer.upper()[0]
    return None


async def mock_project_actions(user_message: str, snapshot: dict[str, object]):
    from app.models.schemas import ProjectActionItem, ProjectExtractionResult

    text = user_message.lower()
    actions: list[ProjectActionItem] = []
    projects = snapshot.get("projects") or []
    if not isinstance(projects, list):
        projects = []

    if "delete" in text and "project" in text:
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            title = str(proj.get("title") or "")
            if title and title.lower() in text:
                actions.append(
                    ProjectActionItem(action="delete_project", project_title=title)
                )
                break

    if "create" in text and "project" in text:
        for line in user_message.splitlines():
            if line.lower().startswith("user:"):
                content = line.split(":", 1)[-1].strip()
                if len(content) > 3:
                    kind = "vocabulary" if "vocab" in text or "english" in text else "general"
                    actions.append(
                        ProjectActionItem(
                            action="create_project",
                            project_title=content[:120],
                            kind=kind,
                            description="Created via chat",
                        )
                    )
                    break

    project_title = _match_project_title(user_message, projects)
    should_add = (
        "add" in text
        or "added" in text
        or "include" in text
        or "words" in text
        or "vocabulary" in text
    )
    if should_add and project_title:
        for term in _extract_vocab_terms(user_message):
            pos = _guess_part_of_speech(term)
            from app.repositories.project_items import pos_list_title

            actions.append(
                ProjectActionItem(
                    action="add",
                    project_title=project_title,
                    list_title=pos_list_title(pos),
                    content=term,
                    part_of_speech=pos,
                )
            )

    quiz_word = _extract_quiz_word(user_message)
    user_answer = _extract_quiz_answer(user_message)
    assistant_confirmed = any(
        phrase in text
        for phrase in (
            "correct",
            "right",
            "nice work",
            "you got it",
            "well done",
            "exactly",
            "1 for 1",
        )
    )
    if quiz_word and user_answer and assistant_confirmed and project_title:
        actions.append(
            ProjectActionItem(
                action="master",
                project_title=project_title,
                list_title="nouns",
                content=quiz_word.strip(),
            )
        )
    elif "master" in text or "learned" in text or "know" in text:
        items = snapshot.get("items") or []
        if isinstance(items, list):
            open_items = [i for i in items if isinstance(i, dict) and not i.get("mastered")]
            if open_items:
                first = open_items[0]
                actions.append(
                    ProjectActionItem(
                        action="master",
                        project_title=str(first.get("project_title") or ""),
                        list_title=str(first.get("list_title") or "General"),
                        content=str(first.get("content") or ""),
                    )
                )

    if not actions:
        return None
    return ProjectExtractionResult(actions=actions)


async def mock_summary(prior_summary: str | None, messages: list[dict[str, str]]) -> str:
    snippets = "; ".join(m.get("content", "")[:40] for m in messages[:3] if m.get("content"))
    base = f"{prior_summary} " if prior_summary else ""
    return (base + f"Earlier the user and assistant discussed: {snippets}.").strip()
