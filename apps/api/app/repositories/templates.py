from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Template


async def list_for_user(
    session: AsyncSession, user_id: UUID, *, limit: int = 100, offset: int = 0
) -> list[Template]:
    """Return user's templates + built-in templates."""
    result = await session.execute(
        select(Template)
        .where(
            (Template.user_id == user_id) | (Template.is_builtin == True)  # noqa: E712
        )
        .order_by(Template.is_builtin.desc(), Template.category.asc(), Template.title.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_by_id(
    session: AsyncSession, template_id: UUID, *, user_id: UUID | None = None
) -> Template | None:
    """Get template by ID, optionally scoped to a user for ownership checks."""
    stmt = select(Template).where(Template.id == template_id)
    if user_id is not None:
        stmt = stmt.where(
            (Template.user_id == user_id) | (Template.is_builtin == True)  # noqa: E712
        )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    user_id: UUID,
    title: str,
    content: str,
    category: str = "general",
) -> Template:
    tpl = Template(user_id=user_id, title=title, content=content, category=category)
    session.add(tpl)
    await session.commit()
    await session.refresh(tpl)
    return tpl


async def update(session: AsyncSession, template: Template, **fields: Any) -> Template:
    for key, value in fields.items():
        if value is not None and hasattr(template, key):
            setattr(template, key, value)
    await session.commit()
    await session.refresh(template)
    return template


async def delete_by_id(session: AsyncSession, template_id: UUID, user_id: UUID) -> bool:
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(Template).where(
                Template.id == template_id,
                Template.user_id == user_id,
                Template.is_builtin == False,  # noqa: E712
            )
        ),
    )
    await session.commit()
    return result.rowcount > 0
