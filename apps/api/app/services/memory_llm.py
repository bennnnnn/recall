"""LLM prompts for memory section extract / merge / rewrite."""

from __future__ import annotations

import json

from app.core.config import Settings
from app.gateways import litellm_gateway, mock_llm
from app.models.schemas import MemorySectionItem, MemorySectionUpdateResult


async def revise_memory_sections(
    settings: Settings,
    transcript: str,
    *,
    existing_sections: dict[str, str] | None = None,
) -> MemorySectionUpdateResult | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_memory_sections(transcript, existing_sections or {})

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
    return await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=MemorySectionUpdateResult,
        max_tokens=1024,
    )


async def merge_memory_section(
    settings: Settings,
    *,
    section_type: str,
    prior_text: str,
) -> MemorySectionItem | None:
    """Merge duplicate facts in one section without dropping distinct facts."""
    clean = prior_text.strip()
    if not clean:
        return None
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_merge_memory_section(section_type, clean)

    messages = [
        {
            "role": "system",
            "content": (
                "You merge long-term memory facts for a personal AI assistant. "
                "Return ONLY JSON (no markdown): "
                '{"type": "profile|preference|project|fact|focus", '
                '"summary": "2-6 sentence paragraph in third person", "confidence": 0.0-1.0}. '
                "Rules:\n"
                "- Preserve EVERY distinct fact from the draft — do not drop names, orgs, "
                "emails, numbers, or preferences.\n"
                "- Deduplicate near-duplicate sentences; merge contradictions sensibly.\n"
                "- Output ONE paragraph (not a bullet list).\n"
                "- Do not invent facts not supported by the draft.\n"
                f"- The section type must remain `{section_type}`."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Section type: {section_type}\n"
                f"Draft facts JSON:\n{json.dumps({'text': clean}, ensure_ascii=False)}"
            ),
        },
    ]
    return await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=MemorySectionItem,
        max_tokens=1024,
    )


async def rewrite_memory_sections(
    settings: Settings,
    sections: dict[str, str],
) -> MemorySectionUpdateResult | None:
    """Rewrite bloated or duplicate section drafts into concise paragraphs.

    Prefer :func:`merge_memory_section` for production consolidation (merge-not-replace).
    """
    if not sections:
        return None
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_rewrite_memory_sections(sections)

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
    return await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=MemorySectionUpdateResult,
        max_tokens=2048,
    )
