from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import model_catalog
from app.models.orm import ProductEvent
from app.models.schemas import ProductEventBatchIn, ProductEventIn
from app.repositories import product_events as product_events_repo
from app.services.md_fence_scan import iter_fences

# The phone sends the two chat events for a sample of turns and says which share
# (code-health audit NET-15): a count divided by its rate is the whole.
_SAMPLE_RATES = frozenset({"1", "0.5", "0.2", "0.1"})

_ALLOWED_PROPERTIES: dict[str, dict[str, frozenset[str]]] = {
    # "welcome" is the offer after the first sign-in, "nudge" the one now and then after it.
    "paywall_viewed": {
        "source": frozenset(
            {"quota", "model_gate", "settings", "voice", "live_talk", "welcome", "nudge", "other"}
        ),
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
        # The error frame's code once a turn started (stream_events); "other" for one
        # with no code, "none" for a turn that did not fail. The phone keeps the same
        # list (turnOutcome.ts); test_turn_outcome_codes.py holds the two together and to
        # every code such a frame carries.
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
                "consent_required",
                "daily_limit",
                "content_blocked",
                "not_found",
                "failed",
                "reply_not_saved",
                "server_restarting",
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
    # A reply's thumbs, recorded by the server when it is saved: the rating ("none" when
    # cleared), the reply's model alias and its kind (``reply_kind``). Never its words.
    "reply_rated": {
        "rating": frozenset({"up", "down", "none"}),
        "model": model_catalog.known_ids() | {"other"},
        "kind": frozenset({"answer", "image", "visual", "code", "search", "text"}),
    },
}

# Fields a newer app adds to an event; one that predates them still sends it
# without. Bucketed like the rest: never a raw millisecond value.
_OPTIONAL_PROPERTIES: dict[str, dict[str, frozenset[str]]] = {
    # Tap on Send -> the user's bubble on screen.
    "chat_ttft": {
        "paint_bucket": frozenset({"lt50", "50_99", "100_249", "250_499", "500_999", "1000_plus"}),
    },
    # The reply's last token -> Send ready again (`stream_end`); "none" when the
    # turn ended another way (Stop, an error).
    "chat_turn_outcome": {
        "send_ready_bucket": frozenset(
            {"none", "lt100", "100_249", "250_499", "500_999", "1000_1999", "2000_plus"}
        ),
    },
}


# Every event name the app records (the CHECK constraint on product_events matches).
EVENT_NAMES: tuple[str, ...] = tuple(_ALLOWED_PROPERTIES)


def _validate_properties(event: ProductEventIn) -> None:
    required = _ALLOWED_PROPERTIES[event.name]
    allowed = {**required, **_OPTIONAL_PROPERTIES.get(event.name, {})}
    keys = set(event.properties)
    if not set(required) <= keys or not keys <= set(allowed):
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


# Fences that draw a picture of the answer (charts, graphs, scenes, molecules, diagrams).
_VISUAL_FENCES = frozenset(
    {"chart", "vega", "vega-lite", "graph", "geometry", "simulation", "mermaid", "smiles",
     "molecule3d", "calculator"}
)  # fmt: skip
# Fences that are the reply's own furniture, not code it wrote.
_NOT_CODE_FENCES = frozenset({"sources", "answer", "worked", "quiz", "clarify", "math", "steps"})


def reply_kind(content: str) -> str:
    """What a reply was, for its rating: a checked answer, a picture, a drawn visual, code,
    a searched answer, or text. Read from the reply alone; only this label leaves it."""
    if "[Image: /attachments/" in content:
        return "image"
    langs = {fence.lang.lower() for fence in iter_fences(content)}
    if langs & {"answer", "worked"}:
        return "answer"
    if langs & _VISUAL_FENCES:
        return "visual"
    if any(lang and lang not in _NOT_CODE_FENCES for lang in langs):
        return "code"
    return "search" if "sources" in langs else "text"


async def record_reply_rating(
    session: AsyncSession, user_id: UUID, *, rating: str | None, model: str | None, content: str
) -> None:
    """The ``reply_rated`` event for a reply just rated; commits."""
    known = model_catalog.known_ids()
    properties = {
        "rating": rating or "none",
        "model": model if model in known else "other",
        "kind": reply_kind(content),
    }
    await product_events_repo.create_batch(
        session, [ProductEvent(user_id=user_id, name="reply_rated", properties=properties)]
    )
