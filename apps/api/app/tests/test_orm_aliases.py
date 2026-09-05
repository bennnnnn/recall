"""Learning aliases and Schedule models preserve their existing DB contracts."""

from app.models.orm import (
    Learning,
    LearningItem,
    Project,
    ProjectItem,
    TodoItem,
)


def test_learning_aliases_and_tablenames() -> None:
    assert Project is Learning
    assert ProjectItem is LearningItem
    assert Learning.__tablename__ == "projects"
    assert LearningItem.__tablename__ == "project_items"


def test_schedule_model_preserves_table_and_foreign_keys() -> None:
    assert TodoItem.__tablename__ == "todo_items"
    assert {
        column.name: next(iter(column.foreign_keys)).target_fullname
        for column in TodoItem.__table__.columns
        if column.foreign_keys
    } == {
        "user_id": "users.id",
        "chat_id": "chats.id",
        "project_id": "projects.id",
    }
