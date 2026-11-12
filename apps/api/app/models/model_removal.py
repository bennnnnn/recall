"""What keeps taking a model out of the catalog safe without a data migration.

A user's saved model switches (``users.enabled_models``), and a phone that kept a copy,
can still name an alias the catalog has since dropped. Read and written, the saved list
keeps only the models the catalog still offers (``current_choices``); a list left with
none is the default, Auto. A request naming an alias the catalog no longer has is Auto
(``requested_choice``), so a stale phone's message still gets an answer; one the plan
does not include is still refused where the turn picks its model.

The routing lanes are data that must name catalog models. The API and the worker check
them as they start (``check_routing_lanes``), so a removal that leaves a lane naming
nothing fails the deploy instead of a turn.
"""

import re

from app.models import model_catalog
from app.models.routing_lanes import ROUTING, RoutingLanes, lane_aliases

AUTO = "auto"

# How a catalog alias is spelled. A name of this shape the catalog no longer has is a
# model removed since the client saved it; anything else was never an alias.
_ALIAS_SHAPE = re.compile(r"[a-z0-9][a-z0-9.\-]{0,63}")


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
    """The model a request names: a catalog alias or Auto, an alias since removed as Auto."""
    if value == AUTO or value in model_catalog.known_ids():
        return value
    if _ALIAS_SHAPE.fullmatch(value):
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
