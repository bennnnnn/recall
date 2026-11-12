"""What keeps taking a model out of the catalog safe without a data migration.

A user's saved model switches (``users.enabled_models``), and a phone that kept a copy,
can still name an alias the catalog has since dropped. Read and written, the saved list
keeps only the models the catalog still offers (``current_choices``); a list left with
none is the default, Auto. A request naming an alias the catalog no longer has is Auto
(``requested_choice``), so a stale phone's message still gets an answer; one the plan
does not include is still refused where the turn picks its model.
"""

import re

from app.models import model_catalog

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
