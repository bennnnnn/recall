"""What chart of their own numbers the user asks for, read by a fast model, drawn by the server.

One short structured call copies the chart's kind and data from the user's words
(``ChartRequest``); ``grounding`` holds every label and number to those words, and ``build``
writes the fence. Nothing here raises into a turn: no read, or a reading that does not hold,
draws nothing.
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.modules.charts.build import chart_fence
from app.modules.charts.grounding import grounded_points, grounded_title, grounded_values
from app.modules.charts.request import ChartRequest

logger = logging.getLogger(__name__)

_MAX_TOKENS = 900
_MAX_CHARS = 2000

_PROMPT = (
    "The user wants a chart of numbers they wrote. Say what to chart, as JSON, copied from "
    "their message.\n"
    "\n"
    "Copy every label and every number exactly as the message writes it, in its order. "
    "Never work a number out, total, round, convert or make one up, and never add a "
    'category the message does not name. When the last message only says "chart it" or '
    "names another kind of chart, the data is in the earlier user message.\n"
    "\n"
    'kind: "bar" (categories compared), "pie" (parts of a whole), "line" (values over '
    'time or in order), "histogram" (how a list of raw values is spread), the kind the '
    'user names when they name one; "none" when the data has more than one number per '
    "category, the numbers are not the user's (a search, an example, a formula y = f(x)), "
    "or there is nothing to chart.\n"
    "Fields:\n"
    '- points (bar, pie, line): [{"label": ..., "value": ...}], one per category, value '
    'the number as written ("1,200", "45%").\n'
    '- values (histogram): every raw value as written, in order (["55", "62", "68"]).\n'
    '- label_name: what the categories are, in the user\'s words ("month"), or "".\n'
    '- value_name: what the numbers measure, in the user\'s words ("sales"), or "".\n'
    "\n"
    'Example: "Make a bar chart of my spending: rent 1200, food 400, transport 150" -> '
    '{"kind": "bar", "points": [{"label": "rent", "value": "1200"}, {"label": "food", '
    '"value": "400"}, {"label": "transport", "value": "150"}], "label_name": "", '
    '"value_name": "spending"}'
)


def _message(question: str, data: str) -> str:
    if not data or data == question:
        return question[:_MAX_CHARS]
    return f"Earlier user message: {data[:_MAX_CHARS]}\n\nLast message: {question[:_MAX_CHARS]}"


async def read_chart(settings: Settings, question: str, data: str) -> ChartRequest | None:
    """The model's reading of the chart, or None when there is no read."""
    from app.core.redis import get_redis_client
    from app.gateways.structured_completion import complete_structured
    from app.services import quota as quota_service

    try:
        if await quota_service.global_spend_exceeded(get_redis_client(), settings):
            return None
        return await complete_structured(
            settings=settings,
            model_alias=ROUTING.chart_read,
            messages=[
                {"role": "system", "content": _PROMPT},
                {"role": "user", "content": _message(question, data)},
            ],
            schema=ChartRequest,
            max_tokens=_MAX_TOKENS,
            timeout_seconds=settings.chart_read_timeout_seconds,
            allow_fallback=False,
            quiet_timeout=True,
        )
    except Exception as exc:  # A read is a hint: any failure draws nothing.
        logger.info("chart read failed (%s)", type(exc).__name__)
        return None


def chart_from_request(request: ChartRequest, data: str) -> str | None:
    """The fence for a reading that holds against the user's words (``data``), else None."""
    label_title = grounded_title(request.label_name, data)
    value_title = grounded_title(request.value_name, data)
    if request.kind == "histogram":
        values = grounded_values(request, data)
        return chart_fence("histogram", values=values, value_title=value_title) if values else None
    if request.kind not in {"bar", "pie", "line"}:
        return None
    pairs = grounded_points(request, data)
    if pairs is None or (request.kind == "pie" and any(value <= 0 for _, value in pairs)):
        return None
    return chart_fence(request.kind, pairs=pairs, label_title=label_title, value_title=value_title)


async def draw_chart(
    question: str, data: str, settings: Settings, *, named: str | None = None
) -> str | None:
    """The fence of the chart of the user's own numbers (``data``: the message that holds
    them, the question itself or an earlier one), or None. ``named``: the kind the user
    asked for, which the reading must be ("a scatter plot" read as a line is no chart)."""
    if not settings.data_charts_enabled or not data.strip():
        return None
    return chart_for_reading(await read_chart(settings, question, data), data, named)


def chart_for_reading(request: ChartRequest | None, data: str, named: str | None) -> str | None:
    """The fence for the read's reading: of the kind the user named, when they named one,
    and holding against their words (``chart_from_request``); else None."""
    if request is None or request.kind == "none":
        return None
    if named is not None and request.kind != named:
        return None
    return chart_from_request(request, data)
