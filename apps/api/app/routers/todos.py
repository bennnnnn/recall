from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.orm import User
from app.models.schemas import TodoCreate, TodoOut, TodoReorderBody, TodoUpdate
from app.services.todos import crud as todos_crud

router = APIRouter(prefix="/todos", tags=["todos"])


def _map_error(exc: todos_crud.TodosError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("", response_model=list[TodoOut])
async def list_todos(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TodoOut]:
    items = await todos_crud.list_todos(session, user)
    return [TodoOut.model_validate(item) for item in items]


@router.get("/topics", response_model=list[str])
async def list_todo_topics(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[str]:
    return await todos_crud.list_topics(session, user)


@router.post("", response_model=TodoOut, status_code=status.HTTP_201_CREATED)
async def create_todo(
    body: TodoCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TodoOut:
    try:
        item = await todos_crud.create_todo(
            session,
            user,
            content=body.content,
            topic=body.topic,
            chat_id=body.chat_id,
            project_id=body.project_id,
            due_at=body.due_at,
        )
    except todos_crud.TodosError as exc:
        raise _map_error(exc) from exc
    return TodoOut.model_validate(item)


@router.post("/reorder", response_model=list[TodoOut])
async def reorder_todos(
    body: TodoReorderBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TodoOut]:
    payload = [(item.id, item.sort_order, item.topic) for item in body.items]
    items = await todos_crud.reorder_todos(session, user, payload)
    return [TodoOut.model_validate(item) for item in items]


@router.patch("/{todo_id}", response_model=TodoOut)
async def update_todo(
    todo_id: UUID,
    body: TodoUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TodoOut:
    try:
        updated = await todos_crud.update_todo(
            session, user, todo_id, body.model_dump(exclude_unset=True)
        )
    except todos_crud.TodosError as exc:
        raise _map_error(exc) from exc
    return TodoOut.model_validate(updated)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(
    todo_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    try:
        await todos_crud.delete_todo(session, user, todo_id)
    except todos_crud.TodosError as exc:
        raise _map_error(exc) from exc


@router.delete("/topic/{topic}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo_topic(
    topic: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete an entire list (topic) in one call — only items without a due_at
    (lists, not reminders) are removed, matching delete_by_topic's semantics.
    """
    try:
        await todos_crud.delete_topic(session, user, topic)
    except todos_crud.TodosError as exc:
        raise _map_error(exc) from exc
