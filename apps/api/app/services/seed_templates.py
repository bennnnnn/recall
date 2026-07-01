"""Built-in templates seeded on startup."""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Template

logger = logging.getLogger(__name__)

BUILTIN_TEMPLATES = [
    {
        "title": "Write an email",
        "content": "Write a professional email about:\n\nTo: \nSubject: \n\nDraft the email body with a clear subject line, polite greeting, concise message, and proper sign-off.",
        "category": "writing",
    },
    {
        "title": "Code review",
        "content": "Review this code for bugs, performance issues, and readability:\n\n```\n[paste code here]\n```\n\nSuggest improvements and explain why.",
        "category": "coding",
    },
    {
        "title": "Debug an issue",
        "content": "I'm seeing this error:\n\n```\n[paste error message]\n```\n\nHere's the relevant code:\n\n```\n[paste code]\n```\n\nWhat's causing this and how do I fix it?",
        "category": "coding",
    },
    {
        "title": "Brainstorm ideas",
        "content": "Brainstorm 5-10 ideas for: [topic]\n\nFor each idea, give a one-line description. Be creative and varied.",
        "category": "general",
    },
    {
        "title": "Summarize text",
        "content": "Summarize the following text in 2-3 key bullet points:\n\n[paste text]\n\nKeep it concise.",
        "category": "general",
    },
    {
        "title": "Explain a concept",
        "content": "Explain [concept] in simple terms. Give a one-sentence overview, then 2-3 key points with examples.",
        "category": "general",
    },
    {
        "title": "Write a social post",
        "content": "Write a [platform] post about:\n\n[topic]\n\nMake it engaging, include relevant hashtags, and keep it under [character limit].",
        "category": "writing",
    },
    {
        "title": "Generate commit message",
        "content": "Write a concise git commit message for these changes:\n\n```\n[git diff or description of changes]\n```\n\nFollow conventional commits format (feat:, fix:, refactor:, etc.).",
        "category": "coding",
    },
    {
        "title": "React Native screen",
        "content": "Create a new React Native screen component called [ScreenName]. Include:\n- StyleSheet at the bottom\n- Safe area insets\n- Standard imports (C colors, Ionicons)\n- Loading and empty states",
        "category": "project",
    },
    {
        "title": "FastAPI endpoint",
        "content": "Create a new FastAPI router for [resource]. Include:\n- GET list endpoint with auth\n- POST create endpoint\n- PATCH update endpoint\n- DELETE endpoint\nFollow the project's existing router patterns.",
        "category": "project",
    },
]


async def seed_templates(session: AsyncSession) -> None:
    """Insert built-in templates only once, idempotent across restarts.

    A partial unique index `ux_templates_builtin_title` (migration 0036) guards
    against the multi-worker race where two workers both pass the existence
    check and try to insert the same builtins. The loser raises
    IntegrityError, which we swallow here so startup never crashes on the race.
    """
    result = await session.execute(
        select(Template).where(Template.is_builtin == True).limit(1)  # noqa: E712
    )
    if result.scalar_one_or_none():
        return  # Already seeded

    try:
        for tpl in BUILTIN_TEMPLATES:
            session.add(
                Template(
                    title=tpl["title"],
                    content=tpl["content"],
                    category=tpl["category"],
                    is_builtin=True,
                )
            )
        await session.commit()
        logger.info("Seeded %d built-in templates", len(BUILTIN_TEMPLATES))
    except IntegrityError:
        # Another worker won the race — the unique index blocked our insert.
        # Roll back the partial add; builtins already exist from the winner.
        await session.rollback()
        logger.info("Built-in templates already seeded by another worker")
