"""Confirm-then-write settings proposals (calendar-proposal style).

No open settings tool — the chat path only stores a validated allowlist
payload in Redis. Writes happen on explicit confirm.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.validation import LOCALE_NAMES
from app.exceptions import ChatServiceError
from app.models.orm import User
from app.repositories import users as users_repo
from app.services import home as home_service
from app.services import memory as memory_service
from app.services import plan as plan_service
from app.services.response_tone import TONE_IDS
from app.services.settings_intent import SettingsChange, SettingsField

logger = logging.getLogger(__name__)

PROPOSAL_TTL_SECONDS = 900
_APPEARANCE_VALUES = frozenset({"light", "dark", "system"})
_MODEL_LABELS = {
    "auto": "Auto",
    "free-chat": "Flash",
    "smart-chat": "Pro",
    "gpt-5.5": "GPT 5.5",
}
_TONE_LABELS = {
    "funny": "Funny",
    "professional": "Professional",
    "casual": "Casual",
    "soft": "Soft",
}
_APPEARANCE_LABELS = {
    "light": "Light",
    "dark": "Dark",
    "system": "System",
}

# Aliases the model emits in a settings_proposal fence that aren't in
# _APPEARANCE_VALUES. "default"/"auto"/"automatic" mean "follow the system
# theme" — the product default. Without this normalization the model's
# "Appearance → Default" proposal is silently dropped by validate_changes
# and the confirm fails with "I couldn't change that setting." — so the user
# can't undo an explicit light/dark choice via chat.
_APPEARANCE_ALIASES: dict[str, str] = {
    "default": "system",
    "auto": "system",
    "automatic": "system",
}


def _normalize_appearance(value: str) -> str:
    return _APPEARANCE_ALIASES.get(value, value)


class SettingsProposalError(ChatServiceError):
    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        super().__init__(detail)
        self.status_code = status_code


def _proposal_key(user_id: UUID, proposal_id: str) -> str:
    return f"settings:proposal:{user_id}:{proposal_id}"


def change_label(field: SettingsField, value: str) -> str:
    if field == "appearance":
        return _APPEARANCE_LABELS.get(value, value)
    if field == "default_model":
        return _MODEL_LABELS.get(value, value)
    if field == "response_tone":
        return _TONE_LABELS.get(value, value)
    if field == "locale":
        return LOCALE_NAMES.get(value, value)
    return value


def field_title(field: SettingsField) -> str:
    return {
        "appearance": "Appearance",
        "default_model": "Model",
        "response_tone": "Tone",
        "locale": "Language",
    }[field]


def _current_value(user: User, field: SettingsField) -> str | None:
    if field == "default_model":
        if plan_service.is_auto_enabled(user):
            return "auto"
        return user.default_model
    if field == "response_tone":
        return user.response_tone
    if field == "locale":
        return user.locale
    return None


def _model_allowed(user: User, settings: Settings, model_id: str) -> bool:
    if model_id == plan_service.AUTO_ALIAS:
        return True
    return model_id in plan_service.allowed_model_ids(user, settings)


def validate_changes(
    user: User,
    settings: Settings,
    changes: list[SettingsChange],
) -> tuple[list[SettingsChange], list[SettingsChange], str | None]:
    """Split into apply / already-set. Returns blocked reason if nothing can apply."""
    apply: list[SettingsChange] = []
    already: list[SettingsChange] = []
    for change in changes:
        if change.field == "appearance":
            # Normalize model-emitted aliases ("default"/"auto") to "system"
            # before the allowlist check so they apply instead of being dropped.
            value = _normalize_appearance(change.value)
            if value not in _APPEARANCE_VALUES:
                continue
            apply.append(SettingsChange("appearance", value))
            continue
        if change.field == "default_model":
            if not _model_allowed(user, settings, change.value):
                return [], [], "That model isn't available on your plan."
            current = _current_value(user, "default_model")
            if current == change.value:
                already.append(change)
            else:
                apply.append(change)
            continue
        if change.field == "response_tone":
            if change.value not in TONE_IDS:
                continue
            if user.response_tone == change.value:
                already.append(change)
            else:
                apply.append(change)
            continue
        if change.field == "locale":
            if change.value not in LOCALE_NAMES:
                continue
            if user.locale == change.value:
                already.append(change)
            else:
                apply.append(change)
    if apply:
        return apply, already, None
    if already:
        return [], already, None
    return [], [], "I couldn't change that setting."


def format_proposal_reply(
    *,
    proposal_id: str,
    apply: list[SettingsChange],
    already: list[SettingsChange],
) -> str:
    if not apply and already:
        labels = ", ".join(change_label(item.field, item.value) for item in already)
        return f"That's already set — {labels}."
    bits = [f"{field_title(item.field)} → {change_label(item.field, item.value)}" for item in apply]
    summary = "; ".join(bits)
    payload = {
        "proposal_id": proposal_id,
        "changes": [
            {
                "field": item.field,
                "value": item.value,
                "label": change_label(item.field, item.value),
            }
            for item in apply
        ],
    }
    fence = json.dumps(payload, ensure_ascii=False)
    return f"I can switch that for you: {summary}.\n\n```settings_proposal\n{fence}\n```"


async def store_proposal(
    redis: Redis,
    user_id: UUID,
    proposal_id: str,
    changes: list[SettingsChange],
) -> None:
    payload = [{"field": item.field, "value": item.value} for item in changes]
    await redis.set(
        _proposal_key(user_id, proposal_id),
        json.dumps(payload),
        ex=PROPOSAL_TTL_SECONDS,
    )


async def load_proposal(
    redis: Redis, user_id: UUID, proposal_id: str
) -> list[SettingsChange] | None:
    raw = await redis.get(_proposal_key(user_id, proposal_id))
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    changes: list[SettingsChange] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        field = item.get("field")
        value = item.get("value")
        if field in {"appearance", "default_model", "response_tone", "locale"} and isinstance(
            value, str
        ):
            changes.append(SettingsChange(field, value))
    return changes or None


async def materialize_settings_reply(
    redis: Redis,
    user: User,
    settings: Settings,
    changes: list[SettingsChange],
) -> str | None:
    apply, already, blocked = validate_changes(user, settings, changes)
    if blocked:
        return blocked
    if not apply:
        return format_proposal_reply(proposal_id="", apply=[], already=already)
    proposal_id = str(uuid4())
    await store_proposal(redis, user.id, proposal_id, apply)
    return format_proposal_reply(proposal_id=proposal_id, apply=apply, already=already)


def _enabled_models_for(user: User, settings: Settings, model_id: str) -> list[str]:
    if model_id == plan_service.AUTO_ALIAS:
        current = user.enabled_models
        if current and plan_service.AUTO_ALIAS in current:
            return list(current)
        pool = plan_service.model_pool(user, settings)
        return plan_service.validate_enabled_models_for_update(
            user, [plan_service.AUTO_ALIAS, *pool], settings
        ) or [plan_service.AUTO_ALIAS]
    return plan_service.validate_enabled_models_for_update(user, [model_id], settings) or [model_id]


async def confirm_proposal(
    session: AsyncSession,
    redis: Redis,
    user: User,
    settings: Settings,
    proposal_id: str,
) -> dict[str, Any]:
    changes = await load_proposal(redis, user.id, proposal_id)
    if changes is None:
        raise SettingsProposalError("Proposal expired or not found.")

    lock_key = _proposal_key(user.id, proposal_id) + ":confirm"
    if not await redis.set(lock_key, "1", ex=120, nx=True):
        raise SettingsProposalError("Update already in progress.")

    try:
        claimed = await redis.getdel(_proposal_key(user.id, proposal_id))
        if claimed is None:
            raise SettingsProposalError("Proposal expired or not found.")

        apply, _already, blocked = validate_changes(user, settings, changes)
        if blocked:
            raise SettingsProposalError(blocked)
        if not apply:
            raise SettingsProposalError("That's already set.")

        fields: dict[str, Any] = {}
        appearance: str | None = None
        for item in apply:
            if item.field == "appearance":
                appearance = item.value
                continue
            if item.field == "default_model":
                fields["default_model"] = item.value
                fields["enabled_models"] = _enabled_models_for(user, settings, item.value)
                continue
            if item.field == "response_tone":
                fields["response_tone"] = item.value
                continue
            if item.field == "locale":
                fields["locale"] = item.value

        updated = user
        if fields:
            memory_toggled = (
                "memory_enabled" in fields and fields["memory_enabled"] != user.memory_enabled
            )
            updated = await users_repo.update(session, user, **fields)
            if memory_toggled:
                await memory_service.invalidate_memory_block(user.id)
            await home_service.invalidate_home_cache(user.id)

        return {
            "user": updated,
            "appearance": appearance,
            "applied": [
                {
                    "field": item.field,
                    "value": item.value,
                    "label": change_label(item.field, item.value),
                }
                for item in apply
            ],
        }
    finally:
        try:
            await redis.delete(lock_key)
        except Exception:
            logger.exception(
                "Settings confirm lock release failed user_id=%s proposal_id=%s",
                user.id,
                proposal_id,
            )
