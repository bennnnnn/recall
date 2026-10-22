from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ProductEvent
from app.models.schemas import ProductEventBatchIn, ProductEventIn
from app.repositories import product_events as product_events_repo

# The phone sends the two chat events for a sample of turns and says which share
# (code-health audit NET-15): a count divided by its rate is the whole.
_SAMPLE_RATES = frozenset({"1", "0.5", "0.2", "0.1"})

_ALLOWED_PROPERTIES: dict[str, dict[str, frozenset[str]]] = {
    "paywall_viewed": {
        "source": frozenset({"quota", "model_gate", "settings", "voice", "live_talk", "other"}),
    },
    # Which paid plan the purchase was for (plan ids, never display names).
    "purchase_started": {"plan": frozenset({"plus", "pro"})},
    "purchase_succeeded": {"plan": frozenset({"plus", "pro"})},
    "purchase_failed": {
        "plan": frozenset({"plus", "pro"}),
        "reason": frozenset({"cancelled", "error"}),
    },
    "push_permission": {
        "status": frozenset({"granted", "denied"}),
    },
    # Bucketed only: no prompt text, chat id, URL, provider error, or arbitrary
    # millisecond string enters product analytics. Server chat timing remains the
    # detailed diagnostic source; this event measures user-bubble -> first token.
    "chat_ttft": {
        "latency_bucket": frozenset(
            {"lt500", "500_999", "1000_1999", "2000_3999", "4000_5999", "6000_plus"}
        ),
        "transport": frozenset({"ws", "sse"}),
        "has_attachment": frozenset({"yes", "no"}),
        "sample_rate": _SAMPLE_RATES,
    },
    # How a chat turn ended, from the phone at done or error. Metadata only:
    # never the prompt, the reply, a query, a chat id or a provider message.
    "chat_turn_outcome": {
        "completion": frozenset({"complete", "stopped", "interrupted", "error"}),
        # The error frame's code (stream_events.error_payload_for_exception);
        # "other" for one with no code, "none" for a turn that did not fail.
        "error_code": frozenset(
            {
                "none",
                "quota_exceeded",
                "spend_cap",
                "model_unavailable",
                "unavailable",
                "busy",
                "attachment_rejected",
                "unknown_model",
                "rate_limited",
                "other",
            }
        ),
        # The first tool the turn showed working (stream_status phases).
        "tool": frozenset(
            {
                "none",
                "searching",
                "calculating",
                "physics",
                "chemistry",
                "reading_files",
                "finding_photo",
                "image_gen",
            }
        ),
        "sample_rate": _SAMPLE_RATES,
    },
}


# Every event name the app records (the CHECK constraint on product_events matches).
EVENT_NAMES: tuple[str, ...] = tuple(_ALLOWED_PROPERTIES)


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
