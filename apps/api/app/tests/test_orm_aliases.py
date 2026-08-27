"""ORM package aliases keep the DB contract while using Learning / List names."""

from app.models.orm import (
    Learning,
    LearningItem,
    ListItem,
    Project,
    ProjectItem,
    TodoItem,
)


def test_learning_aliases_and_tablenames() -> None:
    assert Project is Learning
    assert ProjectItem is LearningItem
    assert Learning.__tablename__ == "projects"
    assert LearningItem.__tablename__ == "project_items"


def test_list_item_alias_and_tablename() -> None:
    assert TodoItem is ListItem
    assert ListItem.__tablename__ == "todo_items"
