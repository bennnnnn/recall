from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models.orm import User
from app.models.schemas import TemplateCreate, TemplateOut, TemplateUpdate
from app.repositories import templates as templates_repo

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[TemplateOut]:
    items = await templates_repo.list_for_user(session, user.id)
    return [TemplateOut.model_validate(item) for item in items]


@router.post("", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: TemplateCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TemplateOut:
    item = await templates_repo.create(
        session,
        user_id=user.id,
        title=body.title,
        content=body.content,
        category=body.category,
    )
    return TemplateOut.model_validate(item)


@router.patch("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: UUID,
    body: TemplateUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> TemplateOut:
    item = await templates_repo.get_by_id(session, template_id, user_id=user.id)
    if not item or item.is_builtin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    updated = await templates_repo.update(session, item, **body.model_dump(exclude_unset=True))
    return TemplateOut.model_validate(updated)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    deleted = await templates_repo.delete_by_id(session, template_id, user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found or cannot be deleted",
        )
