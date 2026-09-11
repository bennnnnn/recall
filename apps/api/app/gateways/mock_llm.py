import asyncio
import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import cast, get_args

from app.core.config import Settings
from app.core.validation import normalize_chat_title

logger = logging.getLogger(__name__)

MOCK_REPLY = (
    "I'm Recall (mock mode). Add OPENROUTER_API_KEY in apps/api/.env "
    "to get real responses. Memory, history, and quotas still work end-to-end."
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


def mock_reply_for_messages(messages: list[dict[str, str]] | None) -> str:
    _ = messages
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


async def mock_memory_facts(user_message: str, existing_facts: list[dict[str, str]]):
    from app.models.schemas import MemoryFactOp, MemoryFactUpdateResult

    del existing_facts
    if len(user_message.strip()) < 10:
        return None
    return MemoryFactUpdateResult(
        ops=[
            MemoryFactOp(
                op="add",
                type="focus",
                text=f"Recently discussed: {user_message[:200]}",
                confidence=0.6,
                sensitivity="normal",
                importance=0.4,
            )
        ]
    )


async def mock_memory_sections(user_message: str, existing_sections: dict[str, str]):
    existing_facts = [
        {"type": memory_type, "text": text}
        for memory_type, text in existing_sections.items()
        if text.strip()
    ]
    return await mock_memory_facts(user_message, existing_facts)


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
    if "add" in text or "remind me" in text:
        # crude: extract after "add" or use whole user line
        for line in user_message.splitlines():
            if line.lower().startswith("user:"):
                content = line.split(":", 1)[-1].strip()
                if len(content) > 3:
                    actions.append(
                        TodoActionItem(
                            action="add",
                            topic="Reminders",
                            content=content[:200],
                            due_at=datetime.now(UTC) + timedelta(hours=1),
                        )
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


async def mock_project_actions(user_message: str, snapshot: dict[str, object]):
    from app.models.schemas import LearningActionItem, LearningExtractionResult, LearningKind

    text = user_message.lower()
    actions: list[LearningActionItem] = []
    projects = snapshot.get("projects") or []
    if not isinstance(projects, list):
        projects = []

    if "delete" in text and "project" in text:
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            title = str(proj.get("title") or "")
            if title and title.lower() in text:
                actions.append(LearningActionItem(action="delete_project", project_title=title))
                break

    if "create" in text and "project" in text:
        for line in user_message.splitlines():
            if line.lower().startswith("user:"):
                content = line.split(":", 1)[-1].strip()
                if len(content) > 3:
                    kind: LearningKind = "language"
                    actions.append(
                        LearningActionItem(
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
                LearningActionItem(
                    action="add",
                    project_title=project_title,
                    list_title="General",
                    content=term,
                )
            )

    if "master" in text or "learned" in text or "know" in text:
        items = snapshot.get("items") or []
        if isinstance(items, list):
            open_items = [i for i in items if isinstance(i, dict) and not i.get("mastered")]
            if open_items:
                first = open_items[0]
                actions.append(
                    LearningActionItem(
                        action="master",
                        project_title=str(first.get("project_title") or ""),
                        list_title=str(first.get("list_title") or "General"),
                        content=str(first.get("content") or ""),
                    )
                )

    if not actions:
        return None
    return LearningExtractionResult(actions=actions)


async def mock_summary(prior_summary: str | None, messages: list[dict[str, str]]) -> str:
    snippets = "; ".join(m.get("content", "")[:40] for m in messages[:3] if m.get("content"))
    base = f"{prior_summary} " if prior_summary else ""
    return (base + f"Earlier the user and assistant discussed: {snippets}.").strip()
