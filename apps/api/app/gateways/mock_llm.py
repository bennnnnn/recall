import asyncio
import logging
import re
from collections.abc import AsyncIterator
from typing import cast, get_args

from app.core.config import Settings
from app.services.chat_titles import normalize_chat_title

logger = logging.getLogger(__name__)

MOCK_REPLY = (
    "I'm Recall (mock mode). Add OPENROUTER_API_KEY in apps/api/.env "
    "to get real responses. Memory, history, and quotas still work end-to-end."
)

MOCK_QUIZ_QUESTION = (
    "**Word:** ubiquitous\n\n"
    "What does it mean?\n\n"
    "A) Extremely rare and hard to find\n"
    "B) Present or found everywhere\n"
    "C) Related to transportation\n"
    "D) A type of musical instrument\n\n"
    "Tap A, B, C, or D — I'll wait for your answer before revealing it.\n\n"
    "```vocab_quiz\n"
    '{"word":"ubiquitous","question":"What does it mean?",'
    '"correct":"B",'
    '"choices":[{"letter":"A","text":"Extremely rare and hard to find"},'
    '{"letter":"B","text":"Present or found everywhere"},'
    '{"letter":"C","text":"Related to transportation"},'
    '{"letter":"D","text":"A type of musical instrument"}]}\n'
    "```"
)

MOCK_QUIZ_RETRY = (
    "Not quite — think about something you see *everywhere*. "
    "Tap another choice on the question above."
)

MOCK_QUIZ_EXHAUSTED = (
    "Out of tries — **ubiquitous** means present or found everywhere (B). "
    "We'll revisit it later.\n\n"
    "Next word:\n\n"
    "**Word:** ephemeral\n\n"
    "What does it mean?\n\n"
    "A) Lasting a very short time\n"
    "B) Extremely large\n"
    "C) Very noisy\n"
    "D) Deeply emotional\n\n"
    "```vocab_quiz\n"
    '{"word":"ephemeral","question":"What does it mean?",'
    '"correct":"A",'
    '"choices":[{"letter":"A","text":"Lasting a very short time"},'
    '{"letter":"B","text":"Extremely large"},'
    '{"letter":"C","text":"Very noisy"},'
    '{"letter":"D","text":"Deeply emotional"}]}\n'
    "```"
)

MOCK_QUIZ_CORRECT_NEXT = (
    "Nice work — **correct!** *Ubiquitous* means present or found everywhere.\n\n"
    "Next word:\n\n"
    "**Word:** ephemeral\n\n"
    "What does it mean?\n\n"
    "A) Lasting a very short time\n"
    "B) Extremely large\n"
    "C) Very noisy\n"
    "D) Deeply emotional\n\n"
    "```vocab_quiz\n"
    '{"word":"ephemeral","question":"What does it mean?",'
    '"correct":"A",'
    '"choices":[{"letter":"A","text":"Lasting a very short time"},'
    '{"letter":"B","text":"Extremely large"},'
    '{"letter":"C","text":"Very noisy"},'
    '{"letter":"D","text":"Deeply emotional"}]}\n'
    "```"
)


def should_mock_llm(settings: Settings) -> bool:
    has_key = bool(settings.openrouter_api_key)
    return settings.mock_llm_enabled and not has_key


# 1x1 PNG — valid image bytes for mock image generation in dev.
_MOCK_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def mock_image_bytes() -> bytes:
    return _MOCK_PNG_BYTES


def _last_user_text(messages: list[dict[str, str]] | None) -> str:
    if not messages:
        return ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content") or "").strip()
    return ""


def _last_assistant_text(messages: list[dict[str, str]] | None) -> str:
    if not messages:
        return ""
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            return str(msg.get("content") or "").strip()
    return ""


def _quiz_attempt_number(messages: list[dict[str, str]] | None) -> int:
    """Count A-D user answers since the most recent quiz fence in the prompt history."""
    from app.services.vocab_quiz import parse_vocab_quiz, quiz_answer_letter

    if not messages:
        return 1
    quiz_idx = -1
    choices: tuple[tuple[str, str], ...] | None = None
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") == "assistant":
            parsed = parse_vocab_quiz(str(msg.get("content") or ""))
            if parsed is not None:
                quiz_idx = i
                choices = parsed.choices
                break
    if quiz_idx < 0:
        return 1
    count = 0
    for msg in messages[quiz_idx + 1 :]:
        if msg.get("role") == "user" and quiz_answer_letter(
            str(msg.get("content") or ""), choices=choices
        ):
            count += 1
    return max(1, count)


def mock_reply_for_messages(messages: list[dict[str, str]] | None) -> str:
    from app.services.vocab_quiz import (
        MAX_QUIZ_TRIES_PER_QUESTION,
        parse_vocab_quiz,
        quiz_answer_letter,
    )

    last_user = _last_user_text(messages)
    lower = last_user.lower()
    # Prefer the open quiz fence (may not be the last assistant after a hint-only miss).
    prior = None
    if messages:
        for msg in reversed(messages):
            if msg.get("role") != "assistant":
                continue
            parsed = parse_vocab_quiz(str(msg.get("content") or ""))
            if parsed is not None:
                prior = parsed
                break
    choices = prior.choices if prior is not None else None
    letter = quiz_answer_letter(last_user, choices=choices)
    if letter:
        if prior and prior.correct:
            if letter == prior.correct.upper():
                return MOCK_QUIZ_CORRECT_NEXT
            if _quiz_attempt_number(messages) >= MAX_QUIZ_TRIES_PER_QUESTION:
                return MOCK_QUIZ_EXHAUSTED
            return MOCK_QUIZ_RETRY
        return MOCK_QUIZ_RETRY
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


async def mock_complete_with_tools(
    *,
    messages: list[dict],
    tools: list[dict],
) -> dict:
    """Dev mock: one web_search tool call when the user asks to search, else no tools."""
    _ = tools
    last = _last_user_text(messages).lower()
    if any(m.get("role") == "tool" for m in messages):
        return {"content": MOCK_REPLY, "tool_calls": []}
    if "search" in last or "look up" in last or "latest" in last:
        return {
            "content": None,
            "tool_calls": [
                {
                    "id": "mock_web_search_1",
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "arguments": '{"query": "mock search"}',
                    },
                }
            ],
        }
    return {"content": MOCK_REPLY, "tool_calls": []}


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


async def mock_merge_memory_section(section_type: str, prior_text: str):
    from app.models.schemas import MemorySectionItem, MemoryType

    valid_memory_types = frozenset(get_args(MemoryType))
    sentences = [part.strip() for part in prior_text.split(".") if part.strip()]
    unique: list[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(sentence)
    summary = ". ".join(unique).strip()
    if summary and not summary.endswith("."):
        summary += "."
    return MemorySectionItem(
        type=cast(
            MemoryType,
            section_type if section_type in valid_memory_types else "fact",
        ),
        summary=summary or prior_text[:300],
        confidence=0.9,
    )


async def mock_rewrite_memory_sections(sections: dict[str, str]):
    from app.models.schemas import MemorySectionItem, MemorySectionUpdateResult

    if not sections:
        return None
    rewritten: list[MemorySectionItem] = []
    for memory_type, text in sections.items():
        item = await mock_merge_memory_section(memory_type, text)
        if item is not None:
            rewritten.append(item)
    return MemorySectionUpdateResult(sections=rewritten)


_MOCK_FACTUAL_LOOKUP = re.compile(
    r"\b("
    r"who is|who was|what is the price|price of|how much|how many|"
    r"population of|net worth|market cap|stock price|when did|when was|"
    r"ceo of|current president|latest version|where can i buy"
    r")\b",
    re.IGNORECASE,
)


async def mock_web_search_classification(
    user_message: str,
    *,
    prior_user_messages: list[str] | None = None,
):
    from app.models.schemas import WebSearchClassification

    del prior_user_messages
    if _MOCK_FACTUAL_LOOKUP.search(user_message):
        return WebSearchClassification(needs_search=True, query=user_message.strip()[:120])
    return WebSearchClassification(needs_search=False)


async def mock_todo_actions(user_message: str, current_todos: list[dict[str, object]]):
    from app.models.schemas import TodoActionItem, TodoExtractionResult

    text = user_message.lower()
    actions: list[TodoActionItem] = []
    if "delete" in text and "list" in text:
        topics = {str(t.get("topic") or "") for t in current_todos if t.get("topic")}
        for topic in sorted(topics):
            if topic and topic.lower() in text:
                actions.append(TodoActionItem(action="delete_list", topic=topic, content=""))
                break
    if "add" in text or "remind me" in text:
        # crude: extract after "add" or use whole user line
        for line in user_message.splitlines():
            if line.lower().startswith("user:"):
                content = line.split(":", 1)[-1].strip()
                if len(content) > 3:
                    actions.append(
                        TodoActionItem(action="add", topic="General", content=content[:200])
                    )
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
            lower.startswith("assistant:") or "add" in lower or "added" in lower or "words" in lower
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


def _extract_quiz_word(transcript: str) -> str | None:
    matches = re.findall(r"(?:\*\*Word:\*\*|Word:)\s*([^\n\[]+)", transcript, flags=re.I)
    if not matches:
        return None
    return matches[-1].strip()


def _extract_quiz_answer(transcript: str) -> str | None:
    from app.services.vocab_quiz import parse_vocab_quiz, quiz_answer_letter

    parsed = parse_vocab_quiz(transcript)
    choices = parsed.choices if parsed is not None else None
    for line in reversed(transcript.splitlines()):
        if not line.lower().startswith("user:"):
            continue
        answer = line.split(":", 1)[-1].strip()
        letter = quiz_answer_letter(answer, choices=choices)
        if letter:
            return letter
    return None


async def mock_project_actions(user_message: str, snapshot: dict[str, object]):
    from app.models.schemas import ProjectActionItem, ProjectExtractionResult, ProjectKind

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
                actions.append(ProjectActionItem(action="delete_project", project_title=title))
                break

    if "create" in text and "project" in text:
        for line in user_message.splitlines():
            if line.lower().startswith("user:"):
                content = line.split(":", 1)[-1].strip()
                if len(content) > 3:
                    kind: ProjectKind = (
                        "vocabulary" if "vocab" in text or "english" in text else "general"
                    )
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
            actions.append(
                ProjectActionItem(
                    action="add",
                    project_title=project_title,
                    list_title="General",
                    content=term,
                )
            )

    quiz_word = _extract_quiz_word(user_message)
    user_answer = _extract_quiz_answer(user_message)
    assistant_said_correct = any(
        phrase in text
        for phrase in (
            "correct!",
            "nice work",
            "you got it",
            "well done",
            "exactly",
            "1 for 1",
        )
    )
    assistant_said_wrong = any(
        phrase in text for phrase in ("not quite", "wrong", "try again", "incorrect")
    )
    if (
        quiz_word
        and user_answer
        and assistant_said_correct
        and not assistant_said_wrong
        and project_title
    ):
        actions.append(
            ProjectActionItem(
                action="master",
                project_title=project_title,
                list_title="General",
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
