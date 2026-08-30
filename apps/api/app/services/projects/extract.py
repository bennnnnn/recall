"""LLM extraction of learning-project actions from a chat turn."""

from __future__ import annotations

import json

from app.core.config import Settings
from app.gateways import litellm_gateway, mock_llm
from app.models.schemas import ProjectExtractionResult


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
                '"create_project|delete_project|set_description|add|start_learning|'
                'master|unmaster|delete|delete_list", '
                '"project_title": "must match a topic title from state when possible", '
                '"kind": "language (vocabulary in a target language)", '
                '"target_language": "ISO 639-1 for language projects: en|es", '
                '"description": "optional description", '
                '"list_title": "chapter/deck name from the project path (e.g. Greetings)", '
                '"content": "one word/phrase per add action", '
                '"definition": "meaning in the user\'s app language", '
                '"example_sentence": "example using the word", '
                '"note": "alias for example_sentence"}]}. '
                "Rules:\n"
                "- Only create language (vocabulary) topics. "
                "Never create trivia, coding, math, or other subject workspaces.\n"
                "- language create_project MUST include target_language. You MAY create a second "
                "language project when the user wants a different language than one they already have.\n"
                "- Do NOT emit create_project for software products, apps to build, repos, or "
                "codebases (e.g. 'dating app project', 'my React app').\n"
                "- add: Do NOT add vocabulary to language projects. Words are preloaded "
                "from the catalog. Use master / start_learning / unmaster on existing words only.\n"
                "- start_learning: when the user FAILED a word/question this turn "
                "(wrong open-ended answer, or gave up after hints). Records it as failed "
                "for today's progress — emit even if the word was already learning.\n"
                "- master / unmaster: update word status.\n"
                "- master: ONLY when the user answered correctly this turn. "
                "NEVER emit master if the user was wrong, the assistant said their "
                "answer was wrong, or the assistant corrected them to a different option.\n"
                "- Return empty actions array if nothing should change."
            ),
        },
        {"role": "user", "content": transcript},
    ]
    return await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=ProjectExtractionResult,
        max_tokens=768,
    )
