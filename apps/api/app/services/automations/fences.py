"""Materialize ```automation JSON fences from assistant replies — chat-based
creation ("create a task to check X every morning at 8am"), mirroring
``services/todos/reminder_fences.py``'s ```reminder pattern. Create-only:
edit/pause/delete already have dedicated My Job list/detail UI.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Automation, User
from app.models.schemas.automations import AutomationFrequency
from app.services.automations.crud import AutomationsError, create_automation

logger = logging.getLogger(__name__)

_AUTOMATION_FENCE = re.compile(r"```automation\s*\n([\s\S]*?)```", re.IGNORECASE)
_INVALID_FENCE = "*Could not create that task — the format was invalid.*"
# Only the first fence in a reply is ever meaningful — a Pro user creating
# two automations in one turn is not a supported flow.
_MAX_PER_TURN = 1


class _AutomationFence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = Field(default=None, max_length=200)
    prompt: str = Field(min_length=1, max_length=2000)
    frequency: AutomationFrequency
    next_run_at: datetime

    @field_validator("next_run_at", mode="before")
    @classmethod
    def _coerce_next_run_at(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        raw = value.strip()
        if raw.endswith(("Z", "z")):
            raw = raw[:-1] + "+00:00"
        if "T" not in raw and " " in raw[:19]:
            raw = raw.replace(" ", "T", 1)
        return raw

    @model_validator(mode="after")
    def _prompt_not_blank(self) -> Self:
        if not self.prompt.strip():
            raise ValueError("prompt cannot be blank")
        return self


def _load_fence_json(raw: str) -> dict[str, object] | None:
    text = raw.strip()
    candidates = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        snippet = text[start : end + 1]
        if snippet != text:
            candidates.append(snippet)
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def _parse_fence(raw: str) -> _AutomationFence | None:
    data = _load_fence_json(raw)
    if data is None:
        return None
    try:
        return _AutomationFence.model_validate(data)
    except ValidationError:
        return None


def format_automation_confirm_fence(automation: Automation) -> str:
    """A small structured fence for mobile to render as a tappable chip
    (frequency + prompt), matching the reminder-fence "saved result" line
    but as a rich block instead of prose — see `fenceRegistry.ts` `automation_created`.
    """
    payload: dict[str, str | None] = {
        "id": str(automation.id),
        "title": automation.title,
        "prompt": automation.prompt,
        "frequency": automation.frequency,
        "next_run_at": automation.next_run_at.isoformat(),
    }
    return f"\n\n```automation_created\n{json.dumps(payload)}\n```"


async def materialize_automation_fences(
    session: AsyncSession,
    *,
    user: User,
    settings: Settings,
    assistant_text: str,
) -> tuple[str, int]:
    """Apply a leading ```automation create fence and strip it from the reply.

    Returns (updated_text, created_count). No fence → unchanged, 0. An
    invalid fence is replaced with an explanatory line rather than left as
    raw JSON. Only the first fence is applied — see `_MAX_PER_TURN`.
    """
    match = _AUTOMATION_FENCE.search(assistant_text)
    if match is None:
        return assistant_text, 0

    parts = [assistant_text[: match.start()], assistant_text[match.end() :]]
    draft = _parse_fence(match.group(1))
    if draft is None:
        logger.warning("Invalid automation fence payload for user_id=%s", user.id)
        updated = (parts[0] + _INVALID_FENCE + parts[1]).strip()
        return re.sub(r"\n{3,}", "\n\n", updated).strip(), 0

    try:
        automation = await create_automation(
            session,
            user,
            settings,
            title=draft.title.strip() if draft.title else None,
            prompt=draft.prompt.strip(),
            frequency=draft.frequency,
            next_run_at=draft.next_run_at,
        )
    except AutomationsError as exc:
        logger.info("Automation fence rejected for user_id=%s: %s", user.id, exc.detail)
        updated = (parts[0] + f"*{exc.detail}.*" + parts[1]).strip()
        return re.sub(r"\n{3,}", "\n\n", updated).strip(), 0

    logger.info("Automation fence applied: user_id=%s automation_id=%s", user.id, automation.id)
    confirm = format_automation_confirm_fence(automation)
    updated = (parts[0].rstrip() + confirm + "\n\n" + parts[1].lstrip()).strip()
    return re.sub(r"\n{3,}", "\n\n", updated).strip(), 1


__all__ = [
    "format_automation_confirm_fence",
    "materialize_automation_fences",
]
