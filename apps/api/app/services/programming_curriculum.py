"""Beginner programming curriculum — chapters with sub-topics (one item per sub-topic)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ProjectItem
from app.repositories import project_items as project_items_repo

# (chapter title, sub-topics) — same journey for every programming language.
# Chapters are broad units; sub-topics are concrete things the learner must cover.
PROGRAMMING_CURRICULUM: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Getting started",
        (
            "What programming is and what code does",
            "How programs run on your computer",
            "Writing and running your first program",
        ),
    ),
    (
        "Variables",
        (
            "What a variable is",
            "What variables are used for",
            "How to create a variable and assign a value",
            "Reading and changing a variable's value",
            "Naming rules (valid names, case sensitivity)",
            "Choosing clear, meaningful names",
        ),
    ),
    (
        "Data types",
        (
            "Strings — storing text",
            "Numbers — integers and decimals",
            "Booleans — true and false",
            "Checking what type a value is",
        ),
    ),
    (
        "Output and comments",
        (
            "Printing output to the screen",
            "Printing variable values",
            "Writing single-line comments",
            "When comments help and when they don't",
        ),
    ),
    (
        "Operators and math",
        (
            "Arithmetic: add, subtract, multiply, divide",
            "Comparison operators (==, !=, <, >)",
            "Combining conditions with and / or / not",
            "Order of operations in expressions",
        ),
    ),
    (
        "Making decisions",
        (
            "if statements — run code when a condition is true",
            "else and else-if branches",
            "Nested conditions",
            "Common decision patterns in real code",
        ),
    ),
    (
        "Loops",
        (
            "for loops — repeat for each item or a set count",
            "while loops — repeat while a condition is true",
            "When to use for vs while",
            "Avoiding infinite loops",
        ),
    ),
    (
        "Functions",
        (
            "What a function is and why we use them",
            "Defining a function",
            "Parameters — passing values in",
            "Return values — sending a result back",
            "Calling functions you've written",
        ),
    ),
    (
        "Lists and collections",
        (
            "What a list is and when to use one",
            "Creating a list and accessing items by index",
            "Adding and removing list items",
            "Looping over every item in a list",
        ),
    ),
    (
        "Errors and debugging",
        (
            "Syntax errors vs runtime errors",
            "Reading an error message and finding the line",
            "Common beginner mistakes (quotes, spelling, indentation)",
            "Using print to trace what your code is doing",
            "Fixing bugs one step at a time",
        ),
    ),
)

PROGRAMMING_CHAPTERS: tuple[str, ...] = tuple(chapter for chapter, _ in PROGRAMMING_CURRICULUM)
CURRICULUM_TOPIC_ORDER: tuple[str, ...] = PROGRAMMING_CHAPTERS


async def seed_programming_curriculum(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
) -> int:
    """Insert starter chapters if the project has no items yet."""
    existing = await project_items_repo.list_for_user(
        session, user_id, project_id=project_id, limit=1
    )
    if existing:
        return 0

    created = 0
    for chapter, topics in PROGRAMMING_CURRICULUM:
        for topic in topics:
            session.add(
                ProjectItem(
                    user_id=user_id,
                    project_id=project_id,
                    list_title=chapter,
                    content=topic,
                    status="new",
                    mastered=False,
                )
            )
            created += 1
    if created:
        await session.commit()
    return created
