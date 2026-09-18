"""Request and response schemas for the Automations feature (Pro-only,
recurring read-only prompts run unattended through the chat turn engine).
"""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AutomationFrequency = Literal["once", "daily", "weekdays", "weekly", "monthly"]
AutomationStatus = Literal["active", "paused", "completed"]
AutomationRunStatus = Literal["ok", "skipped_quota", "error"]


class AutomationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, title="AutomationOut")

    id: UUID
    chat_id: UUID
    prompt: str
    frequency: AutomationFrequency
    next_run_at: datetime
    status: AutomationStatus
    last_run_at: datetime | None = None
    last_run_status: AutomationRunStatus | None = None
    created_at: datetime
    updated_at: datetime


class AutomationCreate(BaseModel):
    model_config = ConfigDict(title="AutomationCreate")

    prompt: str = Field(min_length=1, max_length=2000)
    frequency: AutomationFrequency
    next_run_at: datetime

    @field_validator("prompt")
    @classmethod
    def prompt_cannot_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt cannot be blank")
        return value


class AutomationUpdate(BaseModel):
    model_config = ConfigDict(title="AutomationUpdate")

    prompt: str | None = Field(default=None, min_length=1, max_length=2000)
    frequency: AutomationFrequency | None = None
    next_run_at: datetime | None = None
    # "completed" is a terminal state the worker sets after a one-time run —
    # not something the user can dial back to via PATCH.
    status: Literal["active", "paused"] | None = None

    @field_validator("prompt")
    @classmethod
    def prompt_cannot_be_blank(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("prompt cannot be blank")
        return value

    @model_validator(mode="after")
    def next_run_at_cannot_be_cleared(self) -> Self:
        if "next_run_at" in self.model_fields_set and self.next_run_at is None:
            raise ValueError("next_run_at cannot be cleared")
        return self
