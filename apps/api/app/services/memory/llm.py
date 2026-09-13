"""LLM prompts for atomic memory extract and pair merge."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import Settings
from app.gateways import litellm_gateway, mock_llm
from app.models.schemas import MemoryFactUpdateResult, MemorySectionItem
from app.services.prompt_safety import wrap_untrusted


async def revise_memory_facts(
    settings: Settings,
    transcript: str,
    *,
    existing_facts: list[dict[str, Any]] | None = None,
) -> MemoryFactUpdateResult | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_memory_facts(transcript, existing_facts or [])

    existing = existing_facts or []
    existing_block = json.dumps(existing, ensure_ascii=False, default=str) if existing else "[]"

    messages = [
        {
            "role": "system",
            "content": (
                "You maintain long-term memory about the user as individual facts. "
                "Return ONLY JSON (no markdown): "
                '{"ops": [{"op": "add|update|supersede|delete", '
                '"type": "profile|preference|project|fact|focus", '
                '"text": "one sentence in third person", "confidence": 0.0-1.0, '
                '"sensitivity": "normal|health|finance|legal|relationship|'
                'identity|highly_sensitive", '
                '"importance": 0.0-1.0, "match_text": "existing fact text if updating"}]} . '
                "Type meanings:\n"
                "- profile: name, identity, job, employer, location\n"
                "- preference: how they like to learn, communicate, or use the app\n"
                "- project: active personal projects (not the separate Projects feature)\n"
                "- fact: stable misc facts\n"
                "- focus: current priorities\n\n"
                "Rules:\n"
                "- Extract only facts explicitly stated or confirmed by the User line; "
                "never from assistant inferences, suggestions, or restatements.\n"
                "- Each op is ONE fact — never a paragraph of unrelated ideas.\n"
                "- Return ONLY ops for facts that changed or are new this turn.\n"
                "- On conflicting facts (e.g. moved cities), op=supersede with match_text "
                "of the old fact and text of the new one.\n"
                "- If the User line explicitly asks to remember a fact, add it.\n"
                "- If the User line explicitly asks to forget a fact, op=delete with "
                "match_text of that fact (empty the fact if nothing remains).\n"
                "- Skip small talk. Return empty ops if nothing changed.\n"
                "- Do not invent facts.\n"
                "- Mark health/finance/legal/relationship/identity/highly_sensitive "
                "when the fact is about those topics. Race, religion, politics, "
                "sexual orientation, and sex-life are highly_sensitive."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Existing facts JSON:\n{existing_block}\n\n"
                "New conversation:\n"
                f"{wrap_untrusted('conversation transcript', transcript)}"
            ),
        },
    ]
    return await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=MemoryFactUpdateResult,
        max_tokens=1024,
    )


async def revise_memory_sections(
    settings: Settings,
    transcript: str,
    *,
    existing_sections: dict[str, str] | None = None,
) -> MemoryFactUpdateResult | None:
    """Back-compat name: existing section map is flattened to fact dicts."""
    existing_facts = [
        {"type": memory_type, "text": text}
        for memory_type, text in (existing_sections or {}).items()
        if text.strip()
    ]
    return await revise_memory_facts(settings, transcript, existing_facts=existing_facts)


async def merge_memory_section(
    settings: Settings,
    *,
    section_type: str,
    prior_text: str,
) -> MemorySectionItem | None:
    """Merge two near-duplicate fact texts without dropping distinct facts."""
    clean = prior_text.strip()
    if not clean:
        return None
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_merge_memory_section(section_type, clean)

    messages = [
        {
            "role": "system",
            "content": (
                "You merge two near-duplicate memory facts into one canonical fact. "
                "Return ONLY JSON (no markdown): "
                '{"type": "profile|preference|project|fact|focus", '
                '"summary": "one sentence in third person", "confidence": 0.0-1.0}. '
                "Rules:\n"
                "- Preserve EVERY distinct fact from the draft — do not drop names, orgs, "
                "emails, numbers, or preferences.\n"
                "- Deduplicate near-duplicate sentences.\n"
                "- On contradictions, prefer the newest statement and drop the older one.\n"
                "- Output ONE sentence (not a bullet list).\n"
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
