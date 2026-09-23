"""LLM extraction of To-do actions from a chat turn."""

from __future__ import annotations

import json

from app.core.config import Settings
from app.gateways import litellm_gateway, mock_llm
from app.models.schemas import TodoExtractionResult


async def extract_todo_actions(
    settings: Settings,
    transcript: str,
    current_todos: list[dict[str, object]],
    *,
    user_timezone: str | None = None,
) -> TodoExtractionResult | None:
    if mock_llm.should_mock_llm(settings):
        return await mock_llm.mock_todo_actions(transcript, current_todos)

    snapshot = json.dumps(current_todos, ensure_ascii=False)
    tz_note = user_timezone or "UTC"
    messages = [
        {
            "role": "system",
            "content": (
                "Extract To-do changes requested in this conversation turn. "
                f"User timezone: {tz_note}. "
                "Current To-do JSON (dates are optional):\n"
                f"{snapshot}\n\n"
                "Return ONLY JSON (no markdown): "
                '{"actions": [{"action": '
                '"add|complete|uncheck|delete|set_due|clear_due", '
                '"topic": "General or existing topic", "content": "item text", '
                '"due_at": "ISO-8601 datetime or null", '
                '"recurrence_rule": "daily|weekdays|weekly|monthly or null"}]}. '
                "Rules:\n"
                "- A to-do may be plain and undated. Add grocery, packing, checklist, and "
                "other task requests even when no date was requested; use due_at=null.\n"
                "- For add: content = short title. Use topic=General for an undated item "
                "and topic=Reminders for a dated item unless the user named another topic. "
                "Use the agreed ISO-8601 due_at from the transcript, including prior turns "
                "when the user only said Yes/Sure. Never invent a date. Set recurrence_rule "
                "only when they requested a repeat.\n"
                "- When the assistant confirmed setting a reminder (e.g. Reminder set / "
                "I'll set a reminder) and the transcript has a title + date/time, emit that "
                "add with due_at.\n"
                "- For set_due: due_at is required. Interpret relative dates in the user's "
                "timezone (tomorrow, Friday 5pm). On set_due, include "
                "recurrence_rule when they asked to change the repeat.\n"
                "- For clear_due: match an existing item, remove its date, and also remove "
                "its recurrence. due_at and recurrence_rule must be null.\n"
                "- A recurrence always requires due_at.\n"
                "- Bulk reschedule (all reminders due today → tomorrow): emit one set_due "
                'per affected item, OR a single set_due with content="*" when moving every '
                "open item due today.\n"
                "- If the user says you missed some / only moved one, emit set_due for every "
                "remaining item still due today in the snapshot.\n"
                "- For complete/uncheck/delete: match existing items; use their topic.\n"
                "- Bulk delete overdue: when the user says delete overdue / delete all "
                "overdue reminders, emit one delete action per open overdue item in the "
                "snapshot (match title + topic exactly). There is no separate server-side "
                "bulk wipe — only these explicit delete actions are applied.\n"
                "- Only emit actions the user clearly requested this turn (or confirmed via "
                "Yes after an offer in the transcript).\n"
                "- Return empty actions array if none."
            ),
        },
        {"role": "user", "content": transcript},
    ]
    return await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=messages,
        schema=TodoExtractionResult,
        max_tokens=512,
    )
