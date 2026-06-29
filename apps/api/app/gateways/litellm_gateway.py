import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from litellm import acompletion
from pydantic import BaseModel

from app.core.config import Settings
from app.gateways import mock_llm
from app.models.schemas import (
    MemorySectionUpdateResult,
    ProjectActionItem,
    ProjectExtractionResult,
    TodoExtractionResult,
)
from app.services import model_catalog
from app.services.chat_titles import normalize_chat_title
from app.services.model_catalog import ChatModel

logger = logging.getLogger(__name__)


class ModelUnavailableError(Exception):
    pass


def resolve_model(alias: str) -> str:
    return model_catalog.get(alias).model


def resolve_route(alias: str) -> ChatModel:
    return model_catalog.get(alias)


def _litellm_kwargs(settings: Settings, route: ChatModel) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    api_key = getattr(settings, route.api_key_field, "")
    if not api_key:
        raise ModelUnavailableError(
            f"No API key configured for {route.label} (needs {route.api_key_field})."
        )
    kwargs["api_key"] = api_key
    if route.api_base:
        kwargs["api_base"] = route.api_base
    if route.model.startswith("openrouter/"):
        kwargs.setdefault(
            "extra_headers",
            {
                "HTTP-Referer": "https://github.com/bennnnnn/recall",
                "X-Title": "Recall",
            },
        )
    return kwargs


def _apply_usage(usage: dict[str, int] | None, chunk: Any) -> None:
    if usage is None:
        return
    chunk_usage = getattr(chunk, "usage", None)
    if not chunk_usage:
        return
    prompt = getattr(chunk_usage, "prompt_tokens", None)
    completion = getattr(chunk_usage, "completion_tokens", None)
    if prompt is not None:
        usage["input"] = int(prompt)
    if completion is not None:
        usage["output"] = int(completion)


async def stream_chat_completion(
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    usage: dict[str, int] | None = None,
) -> AsyncIterator[str]:
    if mock_llm.should_mock_llm(settings):
        logger.info("Using mock LLM stream for alias=%s", model_alias)
        async for token in mock_llm.mock_stream(messages=messages):
            yield token
        return

    route = resolve_route(model_alias)
    kwargs = _litellm_kwargs(settings, route)
    try:
        response = await acompletion(
            model=route.model,
            messages=messages,
            stream=True,
            max_tokens=max_tokens,
            stream_options={"include_usage": True},
            **kwargs,
        )
        async for chunk in response:
            _apply_usage(usage, chunk)
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = choices[0].delta
            content = getattr(delta, "content", None) or ""
            if content:
                yield content
    except ModelUnavailableError:
        raise
    except Exception as exc:
        logger.exception("LiteLLM streaming failed for alias=%s", model_alias)
        raise ModelUnavailableError("Model unavailable. Check API keys and try again.") from exc


async def complete_structured[T: BaseModel](
    *,
    settings: Settings,
    model_alias: str,
    messages: list[dict[str, str]],
    schema: type[T],
    max_tokens: int = 256,
) -> T | None:
    if mock_llm.should_mock_llm(settings):
        return None

    route = resolve_route(model_alias)
    kwargs = _litellm_kwargs(settings, route)
    try:
        response = await acompletion(
            model=route.model,
            messages=messages,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            **kwargs,
        )
        raw = response.choices[0].message.content or "{}"
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        return schema.model_validate(data)
    except Exception:
        logger.exception("LiteLLM structured completion failed for alias=%s", model_alias)
        return None


async def generate_title(
    settings: Settings,
    user_message: str,
    assistant_message: str,
) -> str | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_title(user_message)

    messages = [
        {
            "role": "system",
            "content": (
                "You title conversations in 3-6 words. Reply with ONLY the title. "
                "Never use generic labels like 'New chat', 'Untitled', or 'Chat'."
            ),
        },
        {"role": "user", "content": user_message[:300]},
        {"role": "assistant", "content": assistant_message[:300]},
        {"role": "user", "content": "Title?"},
    ]
    route = resolve_route("title-model")
    kwargs = _litellm_kwargs(settings, route)
    try:
        response = await acompletion(
            model=route.model,
            messages=messages,
            max_tokens=20,
            **kwargs,
        )
        raw = (response.choices[0].message.content or "").strip().strip('"').strip("'")
        return normalize_chat_title(raw)
    except Exception:
        logger.exception("Title generation failed")
        return None


async def revise_memory_sections(
    settings: Settings,
    transcript: str,
    *,
    existing_sections: dict[str, str] | None = None,
) -> MemorySectionUpdateResult | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_memory_sections(transcript, existing_sections or {})

    import json

    existing = existing_sections or {}
    existing_block = json.dumps(existing, ensure_ascii=False) if existing else "{}"

    messages = [
        {
            "role": "system",
            "content": (
                "You maintain long-term memory about the user as up to five section summaries. "
                "Return ONLY JSON (no markdown): "
                '{"sections": [{"type": "profile|preference|project|fact|focus", '
                '"summary": "2-4 sentence paragraph in third person", "confidence": 0.0-1.0}]}. '
                "Section meanings:\n"
                "- profile: name, identity, job, employer, location\n"
                "- preference: how they like to learn, communicate, or use the app\n"
                "- project: active personal projects (not the separate Projects feature)\n"
                "- fact: stable misc facts\n"
                "- focus: current priorities\n\n"
                "Rules:\n"
                "- Return ONLY sections that changed or are new this turn.\n"
                "- Each summary is ONE merged paragraph — never a bullet list.\n"
                "- Rewrite the full section when updating; merge duplicates; drop stale facts.\n"
                "- Skip small talk. Return empty sections array if nothing changed."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Existing section summaries JSON:\n{existing_block}\n\n"
                f"New conversation:\n{transcript}"
            ),
        },
    ]
    return await complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=MemorySectionUpdateResult,
        max_tokens=1024,
    )


async def rewrite_memory_sections(
    settings: Settings,
    sections: dict[str, str],
) -> MemorySectionUpdateResult | None:
    """Rewrite bloated or duplicate section drafts into concise paragraphs."""
    if not sections:
        return None
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_rewrite_memory_sections(sections)

    import json

    messages = [
        {
            "role": "system",
            "content": (
                "You clean up long-term memory section drafts for a personal AI assistant. "
                "Return ONLY JSON (no markdown): "
                '{"sections": [{"type": "profile|preference|project|fact|focus", '
                '"summary": "2-4 sentence paragraph in third person", "confidence": 0.0-1.0}]}. '
                "Section meanings:\n"
                "- profile: name, identity, job, employer, location\n"
                "- preference: how they like to learn, communicate, or use the app\n"
                "- project: active personal projects\n"
                "- fact: stable misc facts\n"
                "- focus: current priorities\n\n"
                "Rules:\n"
                "- Return EVERY input section, rewritten.\n"
                "- Each summary is ONE merged paragraph — never a bullet list.\n"
                "- Remove duplicate or near-duplicate sentences; merge contradictions sensibly.\n"
                "- Keep only stable, useful facts; drop noise and repetition.\n"
                "- Do not invent facts not supported by the draft."
            ),
        },
        {
            "role": "user",
            "content": f"Draft section text JSON:\n{json.dumps(sections, ensure_ascii=False)}",
        },
    ]
    return await complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=MemorySectionUpdateResult,
        max_tokens=2048,
    )


async def extract_todo_actions(
    settings: Settings,
    transcript: str,
    current_todos: list[dict[str, object]],
    *,
    user_timezone: str | None = None,
) -> TodoExtractionResult | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_todo_actions(transcript, current_todos)

    import json

    snapshot = json.dumps(current_todos, ensure_ascii=False)
    tz_note = user_timezone or "UTC"
    messages = [
        {
            "role": "system",
            "content": (
                "Extract todo list changes requested in this conversation turn. "
                f"User timezone: {tz_note}. "
                "Current todos JSON:\n"
                f"{snapshot}\n\n"
                "Return ONLY JSON (no markdown): "
                '{"actions": [{"action": "add|complete|uncheck|delete|delete_list|set_due|clear_due", '
                '"topic": "list title", "content": "item text (omit for delete_list)", '
                '"due_at": "ISO-8601 datetime or null"}]}. '
                "Rules:\n"
                "- For add: only when the user gave a clear list title AND item text. "
                "If they want a new list but no title yet, return empty actions.\n"
                "- For add: topic must be the agreed list name (e.g. Groceries, Taxes). "
                "Never invent titles or default to General.\n"
                "- For add/set_due: due_at optional on add; required on set_due. "
                "Interpret relative dates in the user's timezone (tomorrow, Friday 5pm).\n"
                "- Bulk reschedule (all reminders due today → tomorrow): emit one set_due "
                'per affected item, OR a single set_due with content="*" when moving every '
                "open item due today.\n"
                "- If the user says you missed some / only moved one, emit set_due for every "
                "remaining item still due today in the snapshot.\n"
                "- For clear_due: remove due date from the matched item.\n"
                "- For complete/uncheck/delete: match existing items; use their topic.\n"
                "- For delete_list: when the user wants to remove an entire list, emit one "
                "action with that list title; leave content empty.\n"
                "- Only emit actions the user clearly requested this turn.\n"
                "- Return empty actions array if none."
            ),
        },
        {"role": "user", "content": transcript},
    ]
    return await complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=TodoExtractionResult,
        max_tokens=512,
    )


async def extract_project_actions(
    settings: Settings,
    transcript: str,
    snapshot: dict[str, object],
) -> ProjectExtractionResult | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_project_actions(transcript, snapshot)

    state = json.dumps(snapshot, ensure_ascii=False)
    messages = [
        {
            "role": "system",
            "content": (
                "Extract learning-topic workspace changes from this conversation turn "
                "(user message + assistant reply). "
                "Current state JSON:\n"
                f"{state}\n\n"
                "Return ONLY JSON (no markdown): "
                '{"actions": [{"action": '
                '"create_project|delete_project|set_description|set_level|add|start_learning|'
                'master|unmaster|delete|delete_list", '
                '"project_title": "must match a topic title from state when possible", '
                '"kind": "language|programming|learning|general (use language for English/vocab)", '
                '"level": "level1-level6 (for language topics)", '
                '"description": "optional description", '
                '"list_title": "group/list name (e.g. Travel, Nouns)", '
                '"content": "one word/phrase per add action", '
                '"part_of_speech": "noun|verb|adjective|adverb|pronoun|preposition|conjunction|'
                'interjection|phrase|other", '
                '"definition": "meaning in plain English", '
                '"example_sentence": "example using the word", '
                '"note": "alias for example_sentence"}]}. '
                "Rules:\n"
                "- Do NOT emit create_project for software products, apps to build, repos, or "
                "codebases (e.g. 'dating app project', 'my React app') — GitHub coding projects "
                "are a separate future feature.\n"
                "- For programming learning topics: list_title = journey topic (Variables, "
                "Functions, …); content = concept name; use master/start_learning when the user "
                "learns it in chat.\n"
                "- add: ONE action per vocabulary word. part_of_speech is REQUIRED for language "
                "topics (noun|verb|adjective|…). Never mix parts of speech in one group — "
                "list_title is derived automatically (nouns, verbs, …).\n"
                "- add: emit when user asked OR assistant listed new words to add this turn. "
                "Only add words appropriate for the topic's level (level1=beginner basics only).\n"
                "- start_learning / master / unmaster: update word status.\n"
                "- master: REQUIRED when the user answered a vocabulary quiz correctly this turn. "
                "Emit immediately with the quizzed word as content — user must NOT ask to mark it.\n"
                "- set_level: when user moves up (level1=beginner … level6=fluent English skill).\n"
                "- Return empty actions array if nothing should change."
            ),
        },
        {"role": "user", "content": transcript},
    ]

    route = resolve_route("memory-model")
    kwargs = _litellm_kwargs(settings, route)
    try:
        response = await acompletion(
            model=route.model,
            messages=messages,
            max_tokens=768,
            response_format={"type": "json_object"},
            **kwargs,
        )
        raw = (response.choices[0].message.content or "{}").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        actions: list[ProjectActionItem] = []
        for item in data.get("actions") or []:
            if not isinstance(item, dict):
                continue
            try:
                actions.append(ProjectActionItem.model_validate(item))
            except Exception:
                logger.warning("Skipping invalid project action: %s", item)
        return ProjectExtractionResult(actions=actions)
    except Exception:
        logger.exception("Project action extraction failed")
        return None


async def summarize_conversation(
    settings: Settings,
    prior_summary: str | None,
    messages: list[dict[str, str]],
) -> str | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_summary(prior_summary, messages)

    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    parts: list[str] = []
    if prior_summary:
        parts.append(f"Existing summary:\n{prior_summary}")
    parts.append(f"New messages to fold in:\n{transcript}")

    msgs = [
        {
            "role": "system",
            "content": (
                "You compress a conversation into a concise running summary so an "
                "assistant can continue it later. Merge the existing summary with the "
                "new messages. Keep durable facts, decisions, goals, and open threads; "
                "drop chit-chat. Reply with the summary only."
            ),
        },
        {"role": "user", "content": "\n\n".join(parts)},
    ]
    route = resolve_route("memory-model")
    kwargs = _litellm_kwargs(settings, route)
    try:
        response = await acompletion(
            model=route.model,
            messages=msgs,
            max_tokens=settings.summary_max_tokens,
            **kwargs,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        logger.exception("Conversation summarization failed")
        return None
