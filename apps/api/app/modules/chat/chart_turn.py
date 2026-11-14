"""A chart of the user's own numbers: drawn by the server beside the reply, put in its place.

The model wrote these charts as Vega specs with numbers nobody checked (owner decision,
2026-11-13). When the message asks for a bar, pie, line or histogram chart of numbers the
user wrote (``turn_reading.chart.own_data_chart``), the server reads the data while the reply
streams and draws it only when every label and value is the user's (``modules/charts``).
Finalize waits for it at most ``chart_wait_seconds`` and puts it where the model's own chart
of those shapes was, or under the reply. With no chart of its own in time, the model's chart
stays only when its numbers check out the same way; one that does not goes, and no picture
is drawn: a wrong picture is never acceptable. A scatter, a box plot or a chart of several
series is not judged here. Nothing here raises into a turn.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.modules.charts.model_chart import model_chart_kind, model_chart_request
from app.modules.charts.read import MAX_DATA_CHARS, chart_from_request, draw_chart
from app.modules.chat.chart_bodies import parse_chart_body
from app.modules.chat.continuation_subject import exchange_pairs
from app.modules.chat.finalize_subjects import fallback_text
from app.modules.turn_reading.chart_data import named_chart_kind, own_data_chart
from app.services.md_fence_scan import iter_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState
    from app.modules.chat.turn_prep.context import StreamContext

logger = logging.getLogger(__name__)

# The tags a reply's chart is written under (the phone's ``chart`` fence).
_CHART_LANGS = frozenset({"chart", "vega", "vega-lite", "plot"})


def chart_turn(line: str, earlier: Sequence[tuple[str, str]]) -> tuple[str, str | None] | None:
    """The message whose numbers the turn's chart holds to, and the kind the user named;
    None for a turn the server draws no chart for (no numbers of the user's, or a kind of
    chart that is not one of its four)."""
    data = own_data_chart(line, earlier)
    if not data or len(data) > MAX_DATA_CHARS:
        # Longer than the read is shown: a chart of its first part would be a wrong picture.
        return None
    named = named_chart_kind(line) or (named_chart_kind(data) if data != line else None)
    return None if named == "other" else (data, named)


def _turn_of(ctx: StreamContext) -> tuple[str, str | None] | None:
    """``chart_turn`` of the context's message and the chat before it."""
    line = ctx.user_message_content or ""
    return chart_turn(line, exchange_pairs(ctx.recent_messages or [])) if line.strip() else None


def start_chart(settings: Settings, ctx: StreamContext) -> asyncio.Task[str | None] | None:
    """The chart's task, for a turn that asks to chart numbers the user wrote."""
    if not settings.data_charts_enabled or ctx.instant_reply:
        return None
    turn = _turn_of(ctx)
    if turn is None:
        return None
    data, named = turn
    line = ctx.user_message_content or ""
    return asyncio.create_task(draw_chart(line, data, settings, named=named))


def stop_chart(ctx: StreamContext) -> None:
    if ctx.chart is not None and not ctx.chart.done():
        ctx.chart.cancel()


async def _drawn(task: asyncio.Task[str | None], settings: Settings) -> str | None:
    """The server's chart, when it is in within the wait; None otherwise."""
    # Waited on, never awaited: a chart that failed or was stopped is no chart.
    await asyncio.wait([task], timeout=settings.chart_wait_seconds)
    if not task.done():
        task.cancel()
        return None
    if task.cancelled() or task.exception() is not None:
        logger.info("chart task failed: %r", None if task.cancelled() else task.exception())
        return None
    return task.result()


def placed_charts(text: str, drawn: str | None, data: str) -> str:
    """The reply with its charts of the four kinds settled. With the server's chart, it takes
    the first one's place and the others go. Without it, a model chart read here (a temporal
    axis and a Chart.js body are read) is rebuilt from its numbers when they hold and taken
    out when they do not; one of several series is not read, so not judged, and stays, as
    a chart of another kind (a scatter, a box plot) does."""
    pieces: list[str] = []
    cursor = 0
    placed = False
    for fence in iter_fences(text):
        if not fence.closed or fence.lang not in _CHART_LANGS:
            continue
        spec = parse_chart_body(text[fence.body_start : fence.body_end])
        if model_chart_kind(spec) is None:
            continue
        request = model_chart_request(spec)
        if drawn is not None:
            # The user's numbers are one series the server drew: the model's chart of these
            # kinds gives way to it, read or not, so there are never two.
            replacement = "" if placed else drawn
            placed = True
        elif request is None:
            continue  # several series: not read here, so not judged (as a scatter is not)
        else:
            replacement = chart_from_request(request, data) or ""
        pieces.append(text[cursor : fence.start])
        pieces.append(replacement)
        cursor = fence.end
    pieces.append(text[cursor:])
    out = "".join(pieces)
    if drawn is not None and not placed:
        out = f"{out.rstrip()}\n\n{drawn}\n" if out.strip() else f"{drawn}\n"
    return out


async def attach_chart(state: FinalizeState) -> str:
    """The chart of the user's numbers in the reply, the model's unchecked one taken out."""
    task = state.ctx.chart
    if task is None:
        return state.text
    turn = _turn_of(state.ctx)
    if state.was_cancelled or turn is None:
        stop_chart(state.ctx)
        return state.text
    drawn = await _drawn(task, state.settings)
    text = placed_charts(state.text, drawn, turn[0])
    if text == state.text:
        return text
    # Committed, so a later pass that falls back keeps the checked chart.
    state.committed = fallback_text(text, server_text=state.server_text)
    return text
