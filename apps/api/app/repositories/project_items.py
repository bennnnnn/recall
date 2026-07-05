from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ProjectItem

DEFAULT_LIST = "General"
REVIEW_INTERVAL = timedelta(hours=24)

POS_PLURAL: dict[str, str] = {
    "noun": "nouns",
    "verb": "verbs",
    "adjective": "adjectives",
    "adverb": "adverbs",
    "pronoun": "pronouns",
    "preposition": "prepositions",
    "conjunction": "conjunctions",
    "interjection": "interjections",
    "phrase": "phrases",
    "other": "other",
}

POS_SINGULAR: dict[str, str] = {v: k for k, v in POS_PLURAL.items()}
POS_SINGULAR["others"] = "other"


def pos_list_title(part_of_speech: str | None) -> str:
    pos = (part_of_speech or "other").lower().strip()
    if pos in POS_PLURAL:
        return POS_PLURAL[pos]
    if pos in POS_SINGULAR:
        return POS_PLURAL[POS_SINGULAR[pos]]
    if pos.endswith("s"):
        return pos
    return f"{pos}s"


def normalize_pos_key(part_of_speech: str | None) -> str:
    pos = (part_of_speech or "other").lower().strip()
    if pos in POS_PLURAL:
        return pos
    return POS_SINGULAR.get(pos, pos)


# Every stored part_of_speech string that normalizes to each canonical key.
# Used when aligning list_title with part_of_speech for language vocab decks.


def _item_status_label(item: ProjectItem) -> str:
    if item.status:
        return item.status
    return "mastered" if item.mastered else "new"


def _sync_mastered_fields(item: ProjectItem, status: str) -> None:
    item.status = status
    item.mastered = status == "mastered"
    if status == "mastered" and item.mastered_at is None:
        item.mastered_at = datetime.now(UTC)


async def list_for_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    project_id: UUID | None = None,
    project_ids: list[UUID] | None = None,
    limit: int = 500,
) -> list[ProjectItem]:
    stmt = select(ProjectItem).where(ProjectItem.user_id == user_id)
    if project_id is not None:
        stmt = stmt.where(ProjectItem.project_id == project_id)
    elif project_ids:
        stmt = stmt.where(ProjectItem.project_id.in_(project_ids))
    stmt = stmt.order_by(
        ProjectItem.part_of_speech.asc().nullslast(),
        ProjectItem.list_title.asc(),
        ProjectItem.status.asc(),
        ProjectItem.created_at.desc(),
    ).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_by_id(
    session: AsyncSession, item_id: UUID, user_id: UUID, project_id: UUID | None = None
) -> ProjectItem | None:
    stmt = select(ProjectItem).where(ProjectItem.id == item_id, ProjectItem.user_id == user_id)
    if project_id is not None:
        stmt = stmt.where(ProjectItem.project_id == project_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def count_stats(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    *,
    timezone_name: str = "UTC",
) -> dict[str, int]:
    items = await list_for_user(session, user_id, project_id=project_id, limit=5000)
    return stats_from_items(items, timezone_name=timezone_name)


async def list_for_projects(
    session: AsyncSession,
    project_ids: list[UUID],
    *,
    limit: int = 20_000,
) -> list[ProjectItem]:
    """Batched item fetch across many projects (each owned by exactly one
    user) in one query, for callers that need per-project stats for many
    users at once — e.g. count_stats_by_project below."""
    if not project_ids:
        return []
    stmt = select(ProjectItem).where(ProjectItem.project_id.in_(project_ids)).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def count_stats_by_project(
    session: AsyncSession,
    project_ids: list[UUID],
    *,
    timezone_by_project: dict[UUID, str] | None = None,
) -> dict[UUID, dict[str, int]]:
    """Batched count_stats — one query for every project's items instead of
    one query per project, grouped back out per project_id in Python."""
    if not project_ids:
        return {}
    items = await list_for_projects(session, project_ids)
    by_project: dict[UUID, list[ProjectItem]] = {pid: [] for pid in project_ids}
    for item in items:
        by_project.setdefault(item.project_id, []).append(item)
    tz_by_project = timezone_by_project or {}
    return {
        pid: stats_from_items(pid_items, timezone_name=tz_by_project.get(pid, "UTC"))
        for pid, pid_items in by_project.items()
    }


def stats_from_items(
    items: list[ProjectItem],
    *,
    timezone_name: str = "UTC",
) -> dict[str, int]:
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    due_cutoff = now - REVIEW_INTERVAL
    stats: dict[str, Any] = {
        "total": len(items),
        "new_count": 0,
        "learning_count": 0,
        "mastered_count": 0,
        "added_this_week": 0,
        "due_for_review": 0,
        "mastered_today": 0,
        "pending_today": 0,
        "last_mastery_at": None,
    }
    for item in items:
        status = item.status or ("mastered" if item.mastered else "new")
        if status == "mastered":
            stats["mastered_count"] += 1
        elif status == "learning":
            stats["learning_count"] += 1
        else:
            stats["new_count"] += 1
        created = item.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if created >= week_ago:
            stats["added_this_week"] += 1
        if _is_due(item, due_cutoff):
            stats["due_for_review"] += 1

    from app.services.daily_learning import count_today_vocab_stats, last_mastery_at

    mastered_today, pending_today = count_today_vocab_stats(items, timezone_name=timezone_name)
    stats["mastered_today"] = mastered_today
    stats["pending_today"] = pending_today
    stats["last_mastery_at"] = last_mastery_at(items)
    return stats


def _is_due(item: ProjectItem, due_cutoff: datetime) -> bool:
    status = item.status or ("mastered" if item.mastered else "new")
    if status == "new":
        return True
    if status == "learning":
        if item.last_reviewed_at is None:
            return True
        reviewed = item.last_reviewed_at
        if reviewed.tzinfo is None:
            reviewed = reviewed.replace(tzinfo=UTC)
        return reviewed <= due_cutoff
    return False


async def normalize_pos_list_titles(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> int:
    """Align list_title with part_of_speech (nouns, verbs, …) for language vocab."""
    items = await list_for_user(session, user_id, project_id=project_id, limit=5000)
    changed = 0
    for item in items:
        if not item.part_of_speech:
            continue
        expected = pos_list_title(item.part_of_speech)
        if (item.list_title or DEFAULT_LIST).strip().lower() != expected:
            item.list_title = expected
            changed += 1
    if changed:
        await session.commit()
    return changed


async def list_by_activity_date(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    activity_date: date,
    *,
    timezone_name: str = "UTC",
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectItem]:
    """Mastered items whose mastery falls on one local calendar day."""
    from app.services.daily_learning import day_bounds_utc

    start, end = day_bounds_utc(activity_date, timezone_name)
    mastered = or_(ProjectItem.status == "mastered", ProjectItem.mastered.is_(True))
    in_window = or_(
        (ProjectItem.mastered_at >= start) & (ProjectItem.mastered_at < end),
        (ProjectItem.mastered_at.is_(None))
        & (ProjectItem.created_at >= start)
        & (ProjectItem.created_at < end),
    )
    stmt = (
        select(ProjectItem)
        .where(
            ProjectItem.user_id == user_id,
            ProjectItem.project_id == project_id,
            mastered,
            in_window,
        )
        .order_by(ProjectItem.mastered_at.desc().nullslast(), ProjectItem.created_at.desc())
        .offset(max(offset, 0))
        .limit(min(limit, 100))
    )
    return list((await session.execute(stmt)).scalars().all())


async def create(
    session: AsyncSession,
    *,
    user_id: UUID,
    project_id: UUID,
    content: str,
    list_title: str = DEFAULT_LIST,
    note: str | None = None,
    definition: str | None = None,
    example_sentence: str | None = None,
    part_of_speech: str | None = None,
    chat_id: UUID | None = None,
    status: str = "new",
) -> ProjectItem:
    pos = (part_of_speech or "").strip().lower() or None
    if pos:
        normalized_list = pos_list_title(pos)
    else:
        normalized_list = list_title.strip() or DEFAULT_LIST
    example = (example_sentence or note or "").strip() or None
    item = ProjectItem(
        user_id=user_id,
        project_id=project_id,
        content=content.strip(),
        list_title=normalized_list,
        note=example,
        definition=(definition or "").strip() or None,
        example_sentence=example,
        part_of_speech=pos,
        chat_id=chat_id,
        status=status,
        mastered=status == "mastered",
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def update(session: AsyncSession, item: ProjectItem, **fields: Any) -> ProjectItem:
    now = datetime.now(UTC)
    prior_status = _item_status_label(item)
    for key, value in fields.items():
        if hasattr(item, key):
            if key == "list_title" and isinstance(value, str):
                value = value.strip() or DEFAULT_LIST
            if key == "part_of_speech" and isinstance(value, str):
                value = value.strip().lower() or None
            setattr(item, key, value)
    if "status" in fields:
        new_status = str(fields["status"])
        _sync_mastered_fields(item, new_status)
        if new_status != prior_status:
            item.last_reviewed_at = now
            item.review_count = int(item.review_count or 0) + 1
    await session.commit()
    await session.refresh(item)
    return item


async def delete_by_id(session: AsyncSession, item_id: UUID, user_id: UUID) -> bool:
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(ProjectItem).where(ProjectItem.id == item_id, ProjectItem.user_id == user_id)
        ),
    )
    await session.commit()
    return result.rowcount > 0


async def delete_by_list(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    list_title: str,
) -> int:
    normalized = list_title.strip()
    if not normalized:
        return 0
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(ProjectItem).where(
                ProjectItem.user_id == user_id,
                ProjectItem.project_id == project_id,
                func.lower(ProjectItem.list_title) == normalized.lower(),
            )
        ),
    )
    await session.commit()
    return int(result.rowcount or 0)
