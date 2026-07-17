"""LLM extraction of reminder/list actions from a chat turn."""

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
                "Extract Reminders and Lists changes requested in this conversation turn. "
                f"User timezone: {tz_note}. "
                "Current Reminders & Lists JSON:\n"
                f"{snapshot}\n\n"
                "Return ONLY JSON (no markdown): "
                '{"actions": [{"action": "add|complete|uncheck|delete|delete_list|set_due|clear_due", '
                '"topic": "list title", "content": "item text (omit for delete_list)", '
                '"due_at": "ISO-8601 datetime or null"}]}. '
                "Rules:\n"
                "- For add WITHOUT a due date (list item): only when the user gave a clear "
                "list title AND item text. If they want a new list but no title yet, return "
                "empty actions. Topic must be the agreed list name (e.g. Groceries, Taxes) — "
                "never invent list titles.\n"
                "- For add WITH a due date (reminder): content = short reminder title; "
                "due_at = the agreed ISO-8601 datetime from the transcript (including prior "
                'turns when the user only said Yes/Sure). Topic may be "Reminders" or '
                "omitted. Do NOT skip just because there is no grocery-style list title.\n"
                "- When the assistant confirmed setting a reminder (e.g. Reminder set / "
                "I'll set a reminder) and the transcript has a title + date/time, emit that "
                "add with due_at.\n"
                "- For add/set_due: due_at optional on list adds; required on set_due and on "
                "reminder adds. Interpret relative dates in the user's timezone "
                "(tomorrow, Friday 5pm).\n"
                "- Bulk reschedule (all reminders due today → tomorrow): emit one set_due "
                'per affected item, OR a single set_due with content="*" when moving every '
                "open item due today.\n"
                "- If the user says you missed some / only moved one, emit set_due for every "
                "remaining item still due today in the snapshot.\n"
                "- For clear_due: remove due date from the matched item.\n"
                "- For complete/uncheck/delete: match existing items; use their topic.\n"
                "- Bulk delete overdue: when the user says delete overdue / delete all "
                "overdue reminders, emit one delete action per open overdue item in the "
                "snapshot (match title + topic exactly). The server also applies a "
                "deterministic overdue purge for this phrase.\n"
                "- For delete_list: when the user clearly wants to remove an entire list, emit one "
                "action per list title; leave content empty. Skipped server-side if open items remain.\n"
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
