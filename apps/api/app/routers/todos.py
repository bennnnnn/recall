from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.orm import User
from app.models.schemas import TodoCreate, TodoOut, TodoReorderBody, TodoUpdate
from app.repositories import chats as chats_repo
from app.repositories import projects as projects_repo
from app.repositories import todos as todos_repo
from app.services import home as home_service
from app.services.time_context import normalize_due_at

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("", response_model=list[TodoOut])
async def list_todos(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TodoOut]:
    items = await todos_repo.list_for_user(session, user.id)
    return [TodoOut.model_validate(item) for item in items]


@router.get("/topics", response_model=list[str])
async def list_todo_topics(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[str]:
    return await todos_repo.list_topics(session, user.id)


@router.post("", response_model=TodoOut, status_code=status.HTTP_201_CREATED)
async def create_todo(
    body: TodoCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TodoOut:
    # Verify the chat belongs to this user before linking — same cross-user FK
    # concern as chats.project_id. chat_id is optional; only check when set.
    if body.chat_id is not None:
        chat = await chats_repo.get_by_id(session, body.chat_id, user.id)
        if chat is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chat not found")
    if body.project_id is not None:
        project = await projects_repo.get_by_id(session, body.project_id, user.id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project not found")
    # Normalize due_at to UTC using the user's timezone so a naive "9am"
    # from the client is interpreted in the user's local time, not server time.
    # Without this, a naive datetime is stored as-is and reminders fire at the
    # wrong wall-clock hour for any user not on UTC.
    due_at = normalize_due_at(body.due_at, user.timezone)
    item = await todos_repo.create(
        session,
        user_id=user.id,
        content=body.content,
        topic=body.topic,
        chat_id=body.chat_id,
        project_id=body.project_id,
        due_at=due_at,
    )
    await home_service.invalidate_home_cache(user.id)
    return TodoOut.model_validate(item)


@router.post("/reorder", response_model=list[TodoOut])
async def reorder_todos(
    body: TodoReorderBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TodoOut]:
    payload = [(item.id, item.sort_order, item.topic) for item in body.items]
    items = await todos_repo.reorder(session, user.id, payload)
    await home_service.invalidate_home_cache(user.id)
    return [TodoOut.model_validate(item) for item in items]


@router.patch("/{todo_id}", response_model=TodoOut)
async def update_todo(
    todo_id: UUID,
    body: TodoUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TodoOut:
    item = await todos_repo.get_by_id(session, todo_id, user.id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    fields = body.model_dump(exclude_unset=True)
    if "project_id" in fields and fields["project_id"] is not None:
        project = await projects_repo.get_by_id(session, fields["project_id"], user.id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project not found")
    # Normalize due_at to UTC using the user's timezone (same reason as create).
    if "due_at" in fields:
        fields["due_at"] = normalize_due_at(fields["due_at"], user.timezone)
    updated = await todos_repo.update(session, item, **fields)
    await home_service.invalidate_home_cache(user.id)
    return TodoOut.model_validate(updated)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(
    todo_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    deleted = await todos_repo.delete_by_id(session, todo_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
    await home_service.invalidate_home_cache(user.id)


@router.delete("/topic/{topic}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo_topic(
    topic: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete an entire list (topic) in one call — only items without a due_at
    (lists, not reminders) are removed, matching delete_by_topic's semantics.
    Lets the mobile delete a list with one request instead of N per-item DELETEs.
    """
    removed = await todos_repo.delete_by_topic(session, user.id, topic)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="List not found")
    await home_service.invalidate_home_cache(user.id)
