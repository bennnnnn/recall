"""Starter curriculum for programming learning topics — topics map to list_title groups."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ProjectItem
from app.repositories import project_items as project_items_repo

# (topic, concepts) — order is the journey order shown in the app.
PROGRAMMING_CURRICULUM: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Variables", ("Assignment and naming", "Constants and literals", "Variable scope")),
    ("Data types", ("Strings and numbers", "Booleans", "Type conversion")),
    ("Control flow", ("if / else", "for loops", "while loops")),
    ("Functions", ("Defining functions", "Parameters and return values", "Scope in functions")),
    ("Data structures", ("Lists / arrays", "Dictionaries / maps", "Sets or tuples")),
    ("Error handling", ("Reading error messages", "try / except (or equivalent)", "Debugging basics")),
    ("Modules & imports", ("Importing libraries", "Project structure basics")),
    ("Objects & classes", ("Classes and instances", "Methods", "Inheritance basics")),
)

CURRICULUM_TOPIC_ORDER: tuple[str, ...] = tuple(topic for topic, _ in PROGRAMMING_CURRICULUM)


async def seed_programming_curriculum(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
) -> int:
    """Insert starter concepts if the project has no items yet."""
    existing = await project_items_repo.list_for_user(
        session, user_id, project_id=project_id, limit=1
    )
    if existing:
        return 0

    created = 0
    for topic, concepts in PROGRAMMING_CURRICULUM:
        for concept in concepts:
            session.add(
                ProjectItem(
                    user_id=user_id,
                    project_id=project_id,
                    list_title=topic,
                    content=concept,
                    status="new",
                    mastered=False,
                )
            )
            created += 1
    if created:
        await session.commit()
    return created
