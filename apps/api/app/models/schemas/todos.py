from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content: str
    topic: str
    checked: bool
    due_at: datetime | None = None
    sort_order: int | None = None
    chat_id: UUID | None = None
    project_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class TodoCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    topic: str = Field(default="General", min_length=1, max_length=200)
    chat_id: UUID | None = None
    project_id: UUID | None = None
    due_at: datetime | None = None


class TodoUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=1000)
    topic: str | None = Field(default=None, min_length=1, max_length=200)
    checked: bool | None = None
    due_at: datetime | None = None
    sort_order: int | None = Field(default=None, ge=0)
    project_id: UUID | None = None


class TodoReorderItem(BaseModel):
    id: UUID
    sort_order: int = Field(ge=0)
    topic: str | None = Field(default=None, min_length=1, max_length=200)


class TodoReorderBody(BaseModel):
    items: list[TodoReorderItem] = Field(min_length=1, max_length=100)


class TodoActionItem(BaseModel):
    action: Literal[
        "add",
        "complete",
        "uncheck",
        "delete",
        "delete_list",
        "set_due",
        "clear_due",
    ]
    # Empty topic allowed for dated reminder adds (server defaults to Reminders).
    topic: str = Field(default="", max_length=200)
    content: str = Field(default="", max_length=1000)
    due_at: datetime | None = None

    @model_validator(mode="after")
    def validate_action_fields(self) -> Self:
        if self.action == "delete_list":
            if not self.topic.strip():
                raise ValueError("delete_list requires topic")
            return self
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


class TodoExtractionResult(BaseModel):
    actions: list[TodoActionItem] = Field(default_factory=list)
