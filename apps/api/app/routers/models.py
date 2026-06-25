from fastapi import APIRouter, Depends

from app.core.config import Settings
from app.core.deps import get_current_user, get_settings_dep
from app.models.orm import User
from app.models.schemas import ModelInfo
from app.services import model_catalog

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelInfo])
async def list_models(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
) -> list[ModelInfo]:
    """Selectable chat models with provider, pricing, and availability.

    The "Auto" option is not a model — the client offers it separately and the
    backend resolves it per message.
    """
    return [
        ModelInfo(
            id=m.id,
            label=m.label,
            provider=m.provider,
            description=m.description,
            tier=m.tier,
            available=model_catalog.is_available(m, settings),
            input_price_per_m=m.input_price_per_m,
            output_price_per_m=m.output_price_per_m,
        )
        for m in model_catalog.selectable_models()
    ]
