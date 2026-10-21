from datetime import UTC, datetime, time, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, get_redis
from app.core.etag import conditional_json
from app.models.orm import User
from app.modules.todos import crud as todos_crud
from app.modules.todos import proposals as reminder_proposals
from app.modules.todos.schemas import TodoCreate, TodoOut, TodoPageOut, TodoUpdate

router = APIRouter(prefix="/todos", tags=["todos"])


def _map_error(exc: todos_crud.TodosError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


_MAX_TODOS_PAGE = 1000


def _completed_since(days: int) -> datetime:
    """Midnight UTC ``days`` ago: the same all day, so an unchanged list keeps its ETag."""
    return datetime.combine(datetime.now(UTC).date() - timedelta(days=days), time(), UTC)


@router.get("/page", response_model=TodoPageOut)
async def list_todos_page(
    request: Request,
    limit: int = Query(default=_MAX_TODOS_PAGE, ge=1, le=_MAX_TODOS_PAGE),
    cursor: UUID | None = None,
    # Completed rows only from the last this many days; the rest on request
    # (code-health audit NET-16). Omitted: every row.
    completed_days: int | None = Query(default=None, ge=1, le=3650),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response:
    since = _completed_since(completed_days) if completed_days is not None else None
    items, next_cursor = await todos_crud.list_todos_page(
        session, user, limit=limit, cursor=cursor, completed_since=since
    )
    older = (
        since is not None
        and cursor is None
        and await todos_crud.has_older_completed(session, user, since)
    )
    page = TodoPageOut(
        items=[TodoOut.model_validate(item) for item in items],
        next_cursor=next_cursor,
        older_completed=older,
    )
    return conditional_json(request, page)


@router.post("", response_model=TodoOut, status_code=status.HTTP_201_CREATED)
async def create_todo(
    body: TodoCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TodoOut:
    item = await todos_crud.create_todo(
        session,
        user,
        content=body.content,
        topic=body.topic,
        chat_id=body.chat_id,
        due_at=body.due_at,
        recurrence_rule=body.recurrence_rule,
    )
    return TodoOut.model_validate(item)


class ReminderProposalConfirmOut(BaseModel):
    items: list[reminder_proposals.CardItem]
    # The rows the tap wrote and deleted, for the phone to apply without reading its
    # list again (code-health audit NET-16); null when the card was already saved.
    todos: list[TodoOut] | None = None
    deleted_ids: list[UUID] = []


@router.post("/proposals/{proposal_id}/confirm", response_model=ReminderProposalConfirmOut)
async def confirm_reminder_proposal(
    proposal_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ReminderProposalConfirmOut:
    """Save the reminder change a chat card offered. A second tap is a no-op."""
    confirmed = await reminder_proposals.confirm_proposal(
        session, redis, user_id=user.id, proposal_id=proposal_id
    )
    return ReminderProposalConfirmOut(
        items=confirmed.items,
        todos=(
            None
            if confirmed.rows is None
            else [TodoOut.model_validate(row) for row in confirmed.rows]
        ),
        deleted_ids=confirmed.deleted_ids,
    )


@router.patch("/{todo_id}", response_model=TodoOut)
async def update_todo(
    todo_id: UUID,
    body: TodoUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TodoOut:
    updated = await todos_crud.update_todo(
        session, user, todo_id, body.model_dump(exclude_unset=True)
    )
    return TodoOut.model_validate(updated)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(
    todo_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    await todos_crud.delete_todo(session, user, todo_id)
