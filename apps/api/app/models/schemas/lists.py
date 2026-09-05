from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RecurrenceRule = Literal["daily", "weekdays", "weekly", "monthly"]


class ListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, title="TodoOut")

    id: UUID
    content: str
    topic: str
    checked: bool
    due_at: datetime | None = None
    recurrence_rule: RecurrenceRule | None = None
    sort_order: int | None = None
    chat_id: UUID | None = None
    project_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("recurrence_rule", mode="before")
    @classmethod
    def _coerce_recurrence_rule(cls, value: object) -> RecurrenceRule | None:
        if value in ("daily", "weekdays", "weekly", "monthly"):
            return value
        return None


class ListItemCreate(BaseModel):
    model_config = ConfigDict(title="TodoCreate")

    content: str = Field(min_length=1, max_length=1000)
    topic: str = Field(default="General", min_length=1, max_length=200)
    chat_id: UUID | None = None
    project_id: UUID | None = None
    due_at: datetime
    recurrence_rule: RecurrenceRule | None = None

    @field_validator("content")
    @classmethod
    def content_cannot_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content cannot be blank")
        return value

    @model_validator(mode="after")
    def recurrence_needs_due(self) -> Self:
        if self.recurrence_rule is not None and self.due_at is None:
            raise ValueError("recurrence_rule requires due_at")
        if "project_id" in self.model_fields_set:
            raise ValueError("Reminders cannot be linked to a Learning project")
        return self


class ListItemUpdate(BaseModel):
    model_config = ConfigDict(title="TodoUpdate")

    content: str | None = Field(default=None, min_length=1, max_length=1000)
    topic: str | None = Field(default=None, min_length=1, max_length=200)
    checked: bool | None = None
    due_at: datetime | None = None
    recurrence_rule: RecurrenceRule | None = None
    sort_order: int | None = Field(default=None, ge=0)
    project_id: UUID | None = None

    @field_validator("content", "topic", "checked")
    @classmethod
    def supplied_value_cannot_be_null(cls, value: str | bool | None) -> str | bool:
        if value is None:
            raise ValueError("field cannot be null")
        return value

    @field_validator("content")
    @classmethod
    def content_cannot_be_blank(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("content cannot be blank")
        return value

    @model_validator(mode="after")
    def due_at_cannot_be_cleared(self) -> Self:
        if "due_at" in self.model_fields_set and self.due_at is None:
            raise ValueError("due_at cannot be cleared")
        if "project_id" in self.model_fields_set:
            raise ValueError("Reminders cannot be linked to a Learning project")
        return self


class ListReorderItem(BaseModel):
    model_config = ConfigDict(title="TodoReorderItem")

    id: UUID
    sort_order: int = Field(ge=0)
    topic: str | None = Field(default=None, min_length=1, max_length=200)


class ListReorderBody(BaseModel):
    model_config = ConfigDict(title="TodoReorderBody")

    items: list[ListReorderItem] = Field(min_length=1, max_length=100)


class ListActionItem(BaseModel):
    model_config = ConfigDict(title="TodoActionItem")

    action: Literal[
        "add",
        "complete",
        "uncheck",
        "delete",
        "set_due",
        "clear_due",
    ]
    # Empty topic allowed for dated reminder adds (server defaults to Reminders).
    topic: str = Field(default="", max_length=200)
    content: str = Field(default="", max_length=1000)
    due_at: datetime | None = None
    recurrence_rule: RecurrenceRule | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> Self:
        if not self.content.strip():
            raise ValueError("content is required for this action")
        if self.action == "set_due" and self.due_at is None:
            raise ValueError("set_due requires due_at")
        # Dated reminder adds may omit topic; everything else needs a list title.
        if self.action == "add" and self.due_at is not None:
            return self
        if not self.topic.strip():
            raise ValueError("topic is required for this action")
        return self


class ListExtractionResult(BaseModel):
    model_config = ConfigDict(title="TodoExtractionResult")

    actions: list[ListActionItem] = Field(default_factory=list)


TodoOut = ListItemOut
TodoCreate = ListItemCreate
TodoUpdate = ListItemUpdate
TodoReorderItem = ListReorderItem
TodoReorderBody = ListReorderBody
TodoActionItem = ListActionItem
TodoExtractionResult = ListExtractionResult
