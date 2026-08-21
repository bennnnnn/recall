from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ProductEvent
from app.models.schemas import ProductEventBatchIn, ProductEventIn
from app.repositories import product_events as product_events_repo

_ALLOWED_PROPERTIES: dict[str, dict[str, frozenset[str]]] = {
    "paywall_viewed": {
        "source": frozenset({"quota", "model_gate", "settings", "other"}),
    },
    "purchase_started": {},
    "purchase_succeeded": {},
    "purchase_failed": {
        "reason": frozenset({"cancelled", "error"}),
    },
    "push_permission": {
        "status": frozenset({"granted", "denied"}),
    },
}


def _validate_properties(event: ProductEventIn) -> None:
    allowed = _ALLOWED_PROPERTIES[event.name]
    if set(event.properties) != set(allowed):
        raise ValueError(f"Invalid properties for product event {event.name}")
    for key, value in event.properties.items():
        if value not in allowed[key]:
            raise ValueError(f"Invalid {key} for product event {event.name}")


async def record_batch(
    session: AsyncSession,
    user_id: UUID,
    batch: ProductEventBatchIn,
) -> None:
    rows: list[ProductEvent] = []
    for event in batch.events:
        _validate_properties(event)
        rows.append(
            ProductEvent(
                user_id=user_id,
                name=event.name,
                properties=event.properties,
                platform=event.platform,
                app_version=event.app_version,
                installation_id=event.installation_id,
                client_at=event.client_at,
            )
        )

    try:
        await product_events_repo.create_batch(session, rows, commit=False)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
