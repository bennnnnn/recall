"""A turn asks ``writing_request_kind`` and ``is_chart_question`` of its message from a
dozen places, each cleaning it its own way. On a 32 KB message that was 262 ms of the event
loop (PERF-02, 2026-11-13): each now reads a message once a turn."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.readings import begin_turn
from app.modules.turn_reading import chart, writing_kind

_ESSAY = "Here is my essay about trade routes.  " * 800 + "Rewrite it as an email to my boss."


@pytest.mark.asyncio
async def test_the_writing_kind_reads_a_message_once_a_turn() -> None:
    begin_turn()
    with patch.object(writing_kind, "collapse_ws", wraps=writing_kind.collapse_ws) as reads:
        kinds = [writing_kind.writing_request_kind(_ESSAY) for _ in range(12)]
        # Another text (a caller's own cleaning of it) is read on its own.
        kinds.append(writing_kind.writing_request_kind(f"{_ESSAY}\n"))
    assert set(kinds) == {"email"}
    assert reads.call_count == 2


@pytest.mark.asyncio
async def test_the_chart_question_reads_a_message_once_a_turn() -> None:
    message = "Make a bar chart of my sales: Jan 10, Feb 12, Mar 9"
    begin_turn()
    with patch.object(chart, "names_diagram_kind", wraps=chart.names_diagram_kind) as reads:
        answers = {chart.is_chart_question(message), chart.is_chart_question(f"  {message}\n")}
    assert answers == {True}
    assert reads.call_count == 1


def test_outside_a_turn_each_ask_reads_again() -> None:
    """A test or a background job has no turn: nothing is kept between its calls."""
    with patch.object(chart, "names_diagram_kind", wraps=chart.names_diagram_kind) as reads:
        chart.is_chart_question("Make a bar chart of my sales: Jan 10, Feb 12")
        chart.is_chart_question("Make a bar chart of my sales: Jan 10, Feb 12")
    assert reads.call_count == 2
