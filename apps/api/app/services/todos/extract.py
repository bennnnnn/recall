"""LLM extraction of reminder actions from a chat turn."""

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
                "Extract Schedule changes requested in this conversation turn. "
                f"User timezone: {tz_note}. "
                "Current Schedule JSON (dated reminders only):\n"
                f"{snapshot}\n\n"
                "Return ONLY JSON (no markdown): "
                '{"actions": [{"action": "add|complete|uncheck|delete|set_due", '
                '"topic": "Reminders", "content": "item text", '
                '"due_at": "ISO-8601 datetime or null", '
                '"recurrence_rule": "daily|weekdays|weekly|monthly or null"}]}. '
                "Rules:\n"
                "- There is no shopping-list / checklist feature. Never add an item "
                "without due_at. Skip grocery, packing, or undated checklist requests.\n"
                "- For add: content = short title; due_at = the agreed ISO-8601 datetime "
                "from the transcript (including prior turns when the user only said "
                'Yes/Sure). Topic may be "Reminders" or omitted. Set recurrence_rule '
                "when they asked for a repeat (every day / weekdays / every week / "
                "every month).\n"
                "- When the assistant confirmed setting a reminder (e.g. Reminder set / "
                "I'll set a reminder) and the transcript has a title + date/time, emit that "
                "add with due_at.\n"
                "- For add/set_due: due_at is required. Interpret relative dates in the "
                "user's timezone (tomorrow, Friday 5pm).\n"
                "- Bulk reschedule (all reminders due today → tomorrow): emit one set_due "
                'per affected item, OR a single set_due with content="*" when moving every '
                "open item due today.\n"
                "- If the user says you missed some / only moved one, emit set_due for every "
                "remaining item still due today in the snapshot.\n"
                "- Never emit clear_due — Schedule items must keep a due date.\n"
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
