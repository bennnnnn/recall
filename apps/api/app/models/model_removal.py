"""What keeps taking a model out of the catalog safe without a data migration.

A user's saved model switches (``users.enabled_models``), and a phone that kept a copy,
can still name an alias the catalog has since dropped. Read and written, the saved list
keeps only the models the catalog still offers (``current_choices``); a list left with
none is the default, Auto. A request naming an alias the catalog really had and dropped
(``REMOVED_ALIASES``) is Auto (``requested_choice``), so a stale phone's message still
gets an answer; one the plan does not include is still refused where the turn picks its
model. Any other name is refused, as it always was: a typo ("smart-chta") or a name no
alias ever had ("gpt-4o") is a 422, never a silent switch to Auto.

The routing lanes are data that must name catalog models. The API and the worker check
them as they start (``check_routing_lanes``), so a removal that leaves a lane naming
nothing fails the deploy instead of a turn.
"""

from app.models import model_catalog
from app.models.routing_lanes import ROUTING, RoutingLanes, lane_aliases

AUTO = "auto"

# Every alias the catalog has offered and taken out. Removing a model from the catalog
# adds its alias here, so a phone that saved it still sends a message; a name not here
# and not in the catalog was never an alias. Renamed ones are here too: migrations
# 0108, 0109 and 0129 moved the saved choices, but a phone may still hold the old name.
REMOVED_ALIASES: frozenset[str] = frozenset(
    {
        "gemini-flash",
        "glm-4-flash",
        "glm-5.2",
        "glm-5.3",
        "gpt-5.5",
        "gpt-6-sol",
        "kimi-k3",
        "llama-70b",
        "max-chat",
        "mercury-2",
        "minimax-m2",
        "minimax-m3",
        "qwen-3.8-max",
        "qwen-plus",
    }
)


def current_choices(saved: list[str] | None) -> list[str] | None:
    """``saved`` without the models the catalog no longer offers, in order.

    Auto stays. None when no switch is left (or none was saved): the plan's default
    models with Auto on, as the removals before this one migrated it.
    """
    if not saved:
        return None
    offered = {model.id for model in model_catalog.selectable_models()}
    kept = [choice for choice in saved if choice == AUTO or choice in offered]
    return kept or None


def requested_choice(value: str) -> str:
    """The model a request names: a catalog alias or Auto, an alias since removed as Auto.
    Any other name raises ``ValueError`` (a 422 for the request)."""
    if value == AUTO or value in model_catalog.known_ids():
        return value
    if value in REMOVED_ALIASES:
        return AUTO
    raise ValueError(f"Unknown model alias: {value}")


def routing_lane_errors(
    lanes: RoutingLanes = ROUTING, known: frozenset[str] | None = None
) -> list[str]:
    """Each lane that names a model the catalog does not have, and each read lane unknown."""
    known = model_catalog.known_ids() if known is None else known
    errors = [
        f"ROUTING.{where} names {alias!r}, which the model catalog does not have"
        for where, alias in lane_aliases(lanes)
        if alias not in known
    ]
    for subject, chosen in lanes.decided.items():
        errors.extend(
            f"ROUTING.decided[{subject!r}] names the lane {lane!r}, which is no lane"
            for lane in chosen
            if not isinstance(getattr(lanes, lane, None), str)
        )
    return errors


def check_routing_lanes() -> None:
    """Refuse to start while a routing lane names a model the catalog dropped."""
    errors = routing_lane_errors()
    if errors:
        raise RuntimeError(
            "Routing lanes name models the catalog does not have (models/routing_lanes.py): "
            + "; ".join(errors)
        )
