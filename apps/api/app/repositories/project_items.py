from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy import update as sql_update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ProjectItem, QuizMissEvent

DEFAULT_LIST = "General"


def _item_status_label(item: ProjectItem) -> str:
    if item.status:
        return item.status
    return "mastered" if item.mastered else "new"


def _sync_mastered_fields(
    item: ProjectItem, status: str, *, prior_status: str, now: datetime | None = None
) -> None:
    item.status = status
    item.mastered = status == "mastered"
    # BUG FIX (was silent): mastered_at was only backfilled when None, so re-mastering
    # after a miss-triggered demotion left it frozen at the original mastery date —
    # every stats consumer keyed on mastered_at (streaks, daily history, mastered_today)
    # missed the later remastery. Stamp it on every transition INTO "mastered".
    if status == "mastered" and prior_status != "mastered":
        item.mastered_at = now or datetime.now(UTC)


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
        ProjectItem.list_title.asc(),
        ProjectItem.status.asc(),
        ProjectItem.created_at.desc(),
    ).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def list_recent_for_user(
    session: AsyncSession,
    user_id: UUID,
    *,
    project_id: UUID | None = None,
    project_ids: list[UUID] | None = None,
    limit: int = 500,
) -> list[ProjectItem]:
    """Same filters as list_for_user, ordered by recency only.

    BUG FIX (was silent): list_for_user's (list_title, status, created_at
    desc) ordering means the LIMIT window for a user with more items than the
    limit is not guaranteed to include their most-recently-added items —
    apply_project_actions uses a 500-item snapshot of this repo as its
    in-memory match/dedup window (_find_item/_find_project), so a stale
    window hurts dedup/match accuracy for large decks. Kept as a separate
    function rather than changing list_for_user's default order: other
    callers (format_projects_block / group_items / group_trivia_items — the
    deck-browse UI and prompt injection) rely on the existing
    list_title/status grouping order.
    """
    stmt = select(ProjectItem).where(ProjectItem.user_id == user_id)
    if project_id is not None:
        stmt = stmt.where(ProjectItem.project_id == project_id)
    elif project_ids:
        stmt = stmt.where(ProjectItem.project_id.in_(project_ids))
    stmt = stmt.order_by(ProjectItem.created_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def find_quiz_candidates(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    content: str,
    *,
    limit: int = 32,
) -> list[ProjectItem]:
    """Small candidate set for quiz grading — avoids loading the whole deck.

    Exact case-insensitive matches plus a bounded ILIKE neighborhood so the
    service-layer fuzzy fallback (contains / reverse-contains) still works
    without scanning hundreds of rows on the request path.
    """
    needle = content.strip()
    if not needle:
        return []
    pattern = f"%{_like_escape(needle)}%"
    stmt = (
        select(ProjectItem)
        .where(
            ProjectItem.user_id == user_id,
            ProjectItem.project_id == project_id,
            or_(
                func.lower(ProjectItem.content) == needle.lower(),
                ProjectItem.content.ilike(pattern, escape="\\"),
            ),
        )
        .order_by(ProjectItem.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_quiz_exclusion_contents(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    *,
    include_learning: bool = False,
    limit: int = 200,
) -> list[str]:
    """Contents the quiz model must not re-ask (DB ledger, not prompt hope).

    Always includes mastered. When ``include_learning`` is True (trivia), also
    includes previously asked/missed questions so paraphrased duplicates are
    discouraged. Ordered newest-first; capped so the prompt stays bounded.
    """
    if limit < 1:
        return []
    mastered_clause = or_(
        ProjectItem.status == "mastered",
        and_(ProjectItem.mastered.is_(True), ProjectItem.status.is_(None)),
    )
    status_clause = (
        or_(mastered_clause, ProjectItem.status == "learning")
        if include_learning
        else mastered_clause
    )
    stmt = (
        select(ProjectItem.content)
        .where(
            ProjectItem.user_id == user_id,
            ProjectItem.project_id == project_id,
            status_clause,
            ProjectItem.content.is_not(None),
            ProjectItem.content != "",
        )
        .order_by(
            ProjectItem.mastered_at.desc().nullslast(),
            ProjectItem.last_incorrect_at.desc().nullslast(),
            ProjectItem.created_at.desc(),
        )
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    out: list[str] = []
    seen: set[str] = set()
    for content in rows:
        text = (content or "").strip()
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


async def get_by_id(
    session: AsyncSession, item_id: UUID, user_id: UUID, project_id: UUID | None = None
) -> ProjectItem | None:
    stmt = select(ProjectItem).where(ProjectItem.id == item_id, ProjectItem.user_id == user_id)
    if project_id is not None:
        stmt = stmt.where(ProjectItem.project_id == project_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def count_for_project(session: AsyncSession, project_id: UUID, user_id: UUID) -> int:
    """Cheap COUNT(*) for the per-project item cap — avoids loading rows just
    to size-check (unlike count_stats, which loads up to 5000 rows)."""
    stmt = (
        select(func.count())
        .select_from(ProjectItem)
        .where(ProjectItem.user_id == user_id, ProjectItem.project_id == project_id)
    )
    return int((await session.execute(stmt)).scalar_one())


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


async def list_miss_events_for_items(
    session: AsyncSession,
    item_ids: list[UUID],
) -> dict[UUID, list[datetime]]:
    """All logged miss events for the given items, grouped by item_id.

    Backs the day-attribution fix in daily_learning.count_missed_by_date /
    group_missed_items_by_date — see QuizMissEvent's docstring.
    """
    if not item_ids:
        return {}
    stmt = (
        select(QuizMissEvent.item_id, QuizMissEvent.occurred_at)
        .where(QuizMissEvent.item_id.in_(item_ids))
        .order_by(QuizMissEvent.occurred_at.asc())
    )
    rows = (await session.execute(stmt)).all()
    out: dict[UUID, list[datetime]] = {}
    for item_id, occurred_at in rows:
        out.setdefault(item_id, []).append(occurred_at)
    return out


async def list_by_activity_date(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    *,
    start: datetime,
    end: datetime,
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectItem]:
    stmt = (
        select(ProjectItem)
        .where(
            ProjectItem.user_id == user_id,
            ProjectItem.project_id == project_id,
            ProjectItem.mastered.is_(True),
            and_(
                ProjectItem.mastered_at >= start,
                ProjectItem.mastered_at < end,
            ),
        )
        .order_by(ProjectItem.mastered_at.desc().nullslast(), ProjectItem.created_at.desc())
        .offset(max(offset, 0))
        .limit(min(limit, 100))
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_missed_by_activity_date(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    *,
    start: datetime,
    end: datetime,
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectItem]:
    """Still-open misses (not mastered) with a QuizMissEvent in [start, end).

    BUG FIX (was silent): this used to filter on the single mutable
    last_incorrect_at column, so a later miss on the same item silently
    erased which day an earlier miss was attributed to and this page could
    stop showing an item it previously showed — the same underlying bug
    already fixed for the aggregate stats in
    daily_learning.count_missed_by_date/group_missed_items_by_date. Now
    joins against the append-only QuizMissEvent log instead.
    """
    day_misses = (
        select(
            QuizMissEvent.item_id,
            func.max(QuizMissEvent.occurred_at).label("latest_occurred_at"),
        )
        .where(
            QuizMissEvent.user_id == user_id,
            QuizMissEvent.occurred_at >= start,
            QuizMissEvent.occurred_at < end,
        )
        .group_by(QuizMissEvent.item_id)
        .subquery()
    )
    stmt = (
        select(ProjectItem)
        .join(day_misses, ProjectItem.id == day_misses.c.item_id)
        .where(
            ProjectItem.user_id == user_id,
            ProjectItem.project_id == project_id,
            ProjectItem.mastered.is_(False),
        )
        .order_by(
            day_misses.c.latest_occurred_at.desc(),
            ProjectItem.created_at.desc(),
        )
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
    chat_id: UUID | None = None,
    status: str = "new",
    pronunciation_url: str | None = None,
    commit: bool = True,
) -> ProjectItem:
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
        chat_id=chat_id,
        status=status,
        mastered=status == "mastered",
        pronunciation_url=pronunciation_url,
    )
    session.add(item)
    if commit:
        await session.commit()
        await session.refresh(item)
    else:
        await session.flush()
    return item


async def apply_quiz_result(
    session: AsyncSession,
    item: ProjectItem,
    *,
    is_correct: bool,
    new_status: str,
    prior_status: str,
    now: datetime,
    ease_factor: float,
    interval_days: int,
    review_count: int,
    due_at: datetime,
    commit: bool = True,
) -> ProjectItem:
    """Persist a quiz attempt + scheduling fields already computed by the service."""
    # BUG FIX (was silent): quiz_attempts/quiz_correct were read in Python, incremented,
    # then written back — two overlapping requests on the same item (double-tap submit,
    # client retry) could both read the same count and one increment would be lost.
    # Increment atomically in SQL instead so concurrent updates can't clobber each other.
    increments: dict[str, Any] = {"quiz_attempts": ProjectItem.quiz_attempts + 1}
    if is_correct:
        increments["quiz_correct"] = ProjectItem.quiz_correct + 1
    else:
        item.last_incorrect_at = now
        # BUG FIX (was silent): last_incorrect_at is a single mutable column, so a later
        # miss on the same item overwrote which day an earlier miss was attributed to,
        # retroactively changing already-rendered day history. Log every miss as its own
        # event so day-attribution reads (count_missed_by_date) can't regress.
        session.add(QuizMissEvent(item_id=item.id, user_id=item.user_id, occurred_at=now))
    await session.execute(
        sql_update(ProjectItem).where(ProjectItem.id == item.id).values(**increments)
    )

    _sync_mastered_fields(item, new_status, prior_status=prior_status, now=now)
    item.last_reviewed_at = now
    item.review_count = review_count
    item.ease_factor = ease_factor
    item.interval_days = interval_days
    item.due_at = due_at
    if commit:
        await session.commit()
        await session.refresh(item)
    else:
        await session.flush()
        # The atomic UPDATE above bypassed the ORM identity map, so pull the true
        # post-increment counts back before returning `item` to the caller.
        await session.refresh(item, attribute_names=["quiz_attempts", "quiz_correct"])
    return item


async def update(session: AsyncSession, item: ProjectItem, **fields: Any) -> ProjectItem:
    """Dumb field write. SM-2 scheduling belongs in services.projects.items.update_item."""
    now = datetime.now(UTC)
    prior_status = _item_status_label(item)
    for key, value in fields.items():
        if hasattr(item, key):
            if key == "list_title" and isinstance(value, str):
                value = value.strip() or DEFAULT_LIST
            setattr(item, key, value)
    if "status" in fields:
        _sync_mastered_fields(item, str(fields["status"]), prior_status=prior_status, now=now)
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
