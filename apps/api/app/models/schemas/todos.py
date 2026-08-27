"""Compatibility re-exports. Prefer `app.models.schemas.lists`."""

from app.models.schemas.lists import (
    ListActionItem,
    ListExtractionResult,
    ListItemCreate,
    ListItemOut,
    ListItemUpdate,
    ListReorderBody,
    ListReorderItem,
    RecurrenceRule,
    TodoActionItem,
    TodoCreate,
    TodoExtractionResult,
    TodoOut,
    TodoReorderBody,
    TodoReorderItem,
    TodoUpdate,
)

__all__ = [
    "ListActionItem",
    "ListExtractionResult",
    "ListItemCreate",
    "ListItemOut",
    "ListItemUpdate",
    "ListReorderBody",
    "ListReorderItem",
    "RecurrenceRule",
    "TodoActionItem",
    "TodoCreate",
    "TodoExtractionResult",
    "TodoOut",
    "TodoReorderBody",
    "TodoReorderItem",
    "TodoUpdate",
]
