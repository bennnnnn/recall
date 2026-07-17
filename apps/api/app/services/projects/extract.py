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
                '"create_project|delete_project|set_description|set_level|add|start_learning|'
                'master|unmaster|delete|delete_list", '
                '"project_title": "must match a topic title from state when possible", '
                '"kind": "language|trivia (language = English vocabulary; trivia = general knowledge)", '
                '"level": "level1-level6 (for language topics)", '
                '"description": "optional description", '
                '"list_title": "group/list name (e.g. Travel, General)", '
                '"content": "one word/phrase per add action", '
                '"definition": "meaning in plain English", '
                '"example_sentence": "example using the word", '
                '"note": "alias for example_sentence"}]}. '
                "Rules:\n"
                "- Only create language (English vocab) or trivia (general knowledge) topics. "
                "Never create coding/math/other subject workspaces.\n"
                "- Do NOT emit create_project for software products, apps to build, repos, or "
                "codebases (e.g. 'dating app project', 'my React app').\n"
                "- add: ONE action per vocabulary word. Use list_title=General unless the user "
                "named a specific list.\n"
                "- add: emit when user asked OR assistant listed new words to add this turn. "
                "Only add words appropriate for the topic's level (level1=beginner basics only).\n"
                "- start_learning: when the user FAILED a word/question this turn "
                "(wrong open-ended answer, or gave up after hints). Records it as failed "
                "for today's progress — emit even if the word was already learning.\n"
                "- master / unmaster: update word status.\n"
                "- master: ONLY when the user answered correctly this turn. "
                "NEVER emit master if the user was wrong, the assistant said their "
                "answer was wrong, or the assistant corrected them to a different option.\n"
                "- set_level: when user moves up (level1=beginner … level6=fluent English skill).\n"
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
