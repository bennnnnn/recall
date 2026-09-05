"""Owner-scoped catalog writes, deliberately separate from practice mutations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Table, bindparam, delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Project, ProjectItem, User

_CHUNK = 500


async def lock_project(session: AsyncSession, project_id: UUID, user_id: UUID) -> Project | None:
    # Account deletion takes the user lock before deleting children. Keep the
    # same order, then serialize duplicate seeds for this class on its row.
    user = (
        await session.execute(select(User.id).where(User.id == user_id).with_for_update())
    ).scalar_one_or_none()
    if user is None:
        return None
    return (
        await session.execute(
            select(Project)
            .where(
                Project.id == project_id,
                Project.user_id == user_id,
                Project.kind.in_(("language", "vocabulary")),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


async def list_items(session: AsyncSession, project_id: UUID, user_id: UUID) -> list[ProjectItem]:
    return list(
        (
            await session.execute(
                select(ProjectItem)
                .where(
                    ProjectItem.project_id == project_id,
                    ProjectItem.user_id == user_id,
                )
                .order_by(ProjectItem.id)
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )


async def update_contents(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    changes: list[tuple[ProjectItem, dict[str, Any]]],
) -> None:
    # Executemany batches by shape, avoiding a round trip per vocabulary item.
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for item, values in changes:
        if item.catalog_entry_id is None:
            continue
        parameters = {
            "_item_id": item.id,
            "_catalog_id": item.catalog_entry_id,
            **{"_value_" + name: value for name, value in values.items()},
        }
        groups[tuple(sorted(values))].append(parameters)
    table = cast(Table, ProjectItem.__table__)
    for fields, batch in groups.items():
        statement = update(table).where(
            table.c.id == bindparam("_item_id"),
            table.c.user_id == user_id,
            table.c.project_id == project_id,
        )
        statement = statement.where(table.c.catalog_entry_id == bindparam("_catalog_id"))
        statement = statement.values(**{name: bindparam("_value_" + name) for name in fields})
        for offset in range(0, len(batch), _CHUNK):
            await session.execute(statement, batch[offset : offset + _CHUNK])


async def delete_retired(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    active_ids: Sequence[UUID],
) -> None:
    """Remove retired language content inside the caller's locked transaction."""
    owner = exists().where(
        Project.id == project_id,
        Project.user_id == user_id,
        Project.kind.in_(("language", "vocabulary")),
        func.lower(func.trim(func.coalesce(Project.target_language, "en"))).in_(("en", "es")),
    )
    await session.execute(
        delete(ProjectItem)
        .where(
            ProjectItem.user_id == user_id,
            ProjectItem.project_id == project_id,
            owner,
            or_(
                ProjectItem.catalog_entry_id.is_(None),
                ProjectItem.catalog_entry_id.not_in(active_ids),
            ),
        )
        .execution_options(synchronize_session=False)
    )


async def insert_missing(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return
    owner = (
        await session.execute(
            select(Project.id).where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if owner is None:
        return
    for offset in range(0, len(rows), _CHUNK):
        await session.execute(
            pg_insert(ProjectItem)
            .values(
                [
                    {"user_id": user_id, "project_id": project_id, **values}
                    for values in rows[offset : offset + _CHUNK]
                ]
            )
            .on_conflict_do_nothing(index_elements=["project_id", "list_title", "content"])
        )
