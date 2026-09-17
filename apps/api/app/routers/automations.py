from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_settings_dep
from app.models.orm import User
from app.models.schemas import AutomationCreate, AutomationOut, AutomationUpdate
from app.services.automations import crud as automations_crud

router = APIRouter(prefix="/automations", tags=["automations"])


def _map_error(exc: automations_crud.AutomationsError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("", response_model=list[AutomationOut])
async def list_automations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> list[AutomationOut]:
    try:
        items = await automations_crud.list_automations(session, user, settings)
    except automations_crud.AutomationsError as exc:
        raise _map_error(exc) from exc
    return [AutomationOut.model_validate(item) for item in items]


@router.get("/{automation_id}", response_model=AutomationOut)
async def get_automation(
    automation_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> AutomationOut:
    try:
        item = await automations_crud.get_automation(session, user, settings, automation_id)
    except automations_crud.AutomationsError as exc:
        raise _map_error(exc) from exc
    return AutomationOut.model_validate(item)


@router.post("", response_model=AutomationOut, status_code=status.HTTP_201_CREATED)
async def create_automation(
    body: AutomationCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> AutomationOut:
    try:
        item = await automations_crud.create_automation(
            session,
            user,
            settings,
            prompt=body.prompt,
            frequency=body.frequency,
            next_run_at=body.next_run_at,
        )
    except automations_crud.AutomationsError as exc:
        raise _map_error(exc) from exc
    return AutomationOut.model_validate(item)


@router.patch("/{automation_id}", response_model=AutomationOut)
async def update_automation(
    automation_id: UUID,
    body: AutomationUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> AutomationOut:
    try:
        updated = await automations_crud.update_automation(
            session, user, settings, automation_id, body.model_dump(exclude_unset=True)
        )
    except automations_crud.AutomationsError as exc:
        raise _map_error(exc) from exc
    return AutomationOut.model_validate(updated)


@router.delete("/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation(
    automation_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    try:
        await automations_crud.delete_automation(session, user, settings, automation_id)
    except automations_crud.AutomationsError as exc:
        raise _map_error(exc) from exc
