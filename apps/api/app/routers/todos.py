from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.orm import User
from app.models.schemas import TodoCreate, TodoOut, TodoUpdate
from app.repositories import todos as todos_repo

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("", response_model=list[TodoOut])
async def list_todos(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TodoOut]:
    items = await todos_repo.list_for_user(session, user.id)
    return [TodoOut.model_validate(item) for item in items]


@router.post("", response_model=TodoOut, status_code=status.HTTP_201_CREATED)
async def create_todo(
    body: TodoCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TodoOut:
    item = await todos_repo.create(
        session,
        user_id=user.id,
        content=body.content,
        chat_id=body.chat_id,
    )
    return TodoOut.model_validate(item)


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
    updated = await todos_repo.update(session, item, **body.model_dump(exclude_unset=True))
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
