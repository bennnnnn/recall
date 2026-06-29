from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_db
from app.core.deps import get_current_user, get_settings_dep
from app.models.orm import User
from app.models.schemas import HomeScreenOut
from app.services import home as home_service

router = APIRouter(prefix="/home", tags=["home"])


@router.get("", response_model=HomeScreenOut)
async def get_home_screen(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> HomeScreenOut:
    return await home_service.build_home_screen(session, user, settings)
