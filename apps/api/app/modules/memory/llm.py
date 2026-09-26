"""LLM prompts for atomic memory extract and pair merge."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import Settings
from app.gateways import litellm_gateway, mock_llm
from app.models.schemas import MemoryFactUpdateResult, MemorySectionItem
from app.modules.memory.topics import STANDARD_TOPICS
from app.services.prompt_safety import wrap_untrusted

# What belongs in each document, for the model (the UI shows the short summary).
_TOPIC_HINTS = {
    "profile": "who the user is: name, job, employer, school, where they live or come "
    "from, languages they speak",
    "preferences": "how they want replies (length, tone, format, pushback) and how they "
    "like to learn or use the app",
    "interests": "hobbies and interests outside work that they come back to",
    "tech-stack": "languages, frameworks, tools, and services they use in their own work",
    "schedule": "routines, working hours, and how they plan their time",
    "recent-work": "what they are working on lately that is not its own area",
    "goals": "what they are working toward: career, learning, health, life",
    "side-projects": "ideas and smaller things they build",
    "notes": "anything else durable",
}


def _documents_guide() -> str:
    lines = ["Each fact belongs to one memory document, its topic:"]
    lines.extend(f"- {spec.key}: {_TOPIC_HINTS[spec.key]}" for spec in STANDARD_TOPICS)
    lines.append(
        "- area:<slug>: one major named project, job, or part of the user's life, e.g. "
        "area:recall for Recall, an app they are building. Put a fact about a named project "
        "in its area, not in side-projects. Reuse an existing area's topic when the fact "
        "belongs to it. For a new area also give topic_title (its name, e.g. 'Recall') and "
        "topic_summary (one short line, e.g. 'Personal AI chat app built with Expo')."
    )
    return "\n".join(lines)


_OP_SHAPE = (
    '{"ops": [{"op": "add|update|supersede|delete", '
    '"topic": "profile|preferences|interests|tech-stack|schedule|recent-work|goals|'
    'side-projects|notes|area:<slug>", '
    '"topic_title": "new area name, else omit", "topic_summary": "new area line, else omit", '
    '"type": "profile|preference|project|fact|focus", '
    '"text": "one sentence in third person", "confidence": 0.0-1.0, '
    '"sensitivity": "normal|health|finance|legal|relationship|identity|highly_sensitive", '
    '"importance": 0.0-1.0, "match_text": "existing fact text if updating"}]}'
)

_SENSITIVITY_RULES = (
    "- sensitivity says what the fact reveals about the user's private life. "
    "normal: name, job, employer, school, city, home country, languages, "
    "projects, tools, interests, schedule, and reply preferences. "
    "health: their physical or mental health. finance: their income, debts, "
    "or accounts. legal: their own legal matters. relationship: their romantic "
    "life or partner. identity: gender identity, immigration status, or "
    "disability. highly_sensitive: race or ethnicity, religion, politics, "
    "sexual orientation, and sex life.\n"
    "- Label the user's life, not the subject of their work: building a dating "
    "app or a health tracker is a normal project fact."
)


async def revise_memory_facts(
    settings: Settings,
    transcript: str,
    *,
    existing_facts: list[dict[str, Any]] | None = None,
    existing_areas: list[dict[str, Any]] | None = None,
) -> MemoryFactUpdateResult | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_memory_facts(transcript, existing_facts or [])

    existing = existing_facts or []
    existing_block = json.dumps(existing, ensure_ascii=False, default=str) if existing else "[]"
    areas_block = json.dumps(existing_areas or [], ensure_ascii=False, default=str)

    messages = [
        {
            "role": "system",
            "content": (
                "You maintain long-term memory about the user as individual facts, "
                "grouped into documents the user can read. "
                f"Return ONLY JSON (no markdown): {_OP_SHAPE} .\n"
                f"{_documents_guide()}\n\n"
                "Type meanings (the topic usually decides it):\n"
                "- profile: who the user is. "
                "A name is theirs only when they claim it ('my name is', 'I'm', "
                "'call me', 'I go by'). The only name sentence is "
                "'User's name is John' or 'User's name is John; also goes by X.'\n"
                "- preference: how they like to learn, communicate, or use the app\n"
                "- project: what the user is working on or building, including one they name\n"
                "- fact: stable misc facts\n"
                "- focus: current priorities\n\n"
                "Rules:\n"
                "- Use only what the User lines state or clearly show about the user; "
                "never assistant inferences, suggestions, or restatements.\n"
                "- Capture durable context the user reveals while asking for help, not only "
                "in introductions: the projects they build (with their names), the stack "
                "they build with, their job and role, goals, routines, and interests they "
                "come back to. 'Fix the drawer in my Expo app Recall' says the user builds "
                "Recall with Expo.\n"
                "- A one-off question is not a fact about the user: asking the capital of "
                "France is not an interest in France.\n"
                "- Natural phrasing still counts: 'As a software engineer at Uber' is an "
                "explicit job/employer fact even without 'I am'.\n"
                "- Store durable reply-style feedback as a preference when the user describes "
                "what they prefer, asks for an ongoing behavior, or corrects how the assistant "
                "usually responds. Do not store formatting requested only for the current task.\n"
                "- Each op is ONE fact — never a paragraph of unrelated ideas.\n"
                "- Return ONLY ops for facts that changed or are new this turn.\n"
                "- On conflicting facts (e.g. moved cities), op=supersede with match_text "
                "of the old fact and text of the new one.\n"
                "- Distinguish current facts from aspirations and hypotheticals. For example, "
                "'I work at Uber but want to move to Google' keeps Uber as the current employer "
                "and adds Google as a career goal; it must not claim the user works at Google.\n"
                "- If the User line explicitly asks to remember a fact, add it.\n"
                "- If the User line explicitly asks to forget a fact, op=delete with "
                "match_text of that fact (empty the fact if nothing remains).\n"
                "- When the user says what they are working on, building, or focusing on, "
                "add that project or focus fact. Do not drop it and do not treat it as "
                "the Learning projects feature.\n"
                "- Skip small talk. Return empty ops only when the user stated nothing "
                "durable about themselves.\n"
                "- Do not invent facts.\n"
                "- Never store a name from a word problem, story, example, or "
                "anyone other than the user. 'Bebe has 2 pens and gives them to "
                "Cal' is not the user's name.\n"
                f"{_SENSITIVITY_RULES}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Existing facts JSON:\n{existing_block}\n\n"
                f"Existing areas JSON:\n{areas_block}\n\n"
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
        # Room for several ops; a reply cut off mid-JSON is discarded whole.
        max_tokens=2048,
    )


async def instruct_memory(
    settings: Settings,
    instruction: str,
    *,
    existing_facts: list[dict[str, Any]],
    existing_areas: list[dict[str, Any]],
    focus_topic: str | None = None,
) -> MemoryFactUpdateResult | None:
    """Turn the user's own edit ("keep lists under five things") into memory ops."""
    if mock_llm.should_mock_llm(settings):
        return MemoryFactUpdateResult(ops=[], reply="Memory editing needs a live model.")

    focus = (
        f"The user is looking at the {focus_topic} document; prefer it for new facts and "
        "edits unless the instruction clearly belongs elsewhere.\n"
        if focus_topic
        else ""
    )
    messages = [
        {
            "role": "system",
            "content": (
                "The user is editing their long-term memory directly. Turn their "
                "instruction into ops over the existing facts. Return ONLY JSON (no "
                f"markdown): {_OP_SHAPE[:-2]}], "
                '"reply": "one short sentence to the user"} .\n'
                f"{_documents_guide()}\n\n"
                "Rules:\n"
                "- The instruction is the user speaking about themselves, so it counts as "
                "stated. Follow it exactly and do not invent anything beyond it.\n"
                "- How they want replies ('you can disagree with me more', 'keep lists under "
                "five things') is a preferences fact.\n"
                "- To correct a fact, op=update with match_text of that fact. To remove one, "
                "op=delete with match_text. To move one to another document, op=update with "
                "the new topic. To add, op=add.\n"
                "- Each op is ONE fact in third person ('User prefers ...').\n"
                "- reply: one short plain sentence saying what changed, or why nothing did "
                "(for example when the message is not about memory). No markdown.\n"
                f"{focus}"
                f"{_SENSITIVITY_RULES}"
            ),
        },
        {
            "role": "user",
            "content": (
                "Existing facts JSON:\n"
                f"{json.dumps(existing_facts, ensure_ascii=False, default=str)}\n\n"
                "Existing areas JSON:\n"
                f"{json.dumps(existing_areas, ensure_ascii=False, default=str)}\n\n"
                f"{wrap_untrusted('memory instruction', instruction)}"
            ),
        },
    ]
    return await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=MemoryFactUpdateResult,
        max_tokens=2048,
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
