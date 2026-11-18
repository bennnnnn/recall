"""A graph drawn in text characters is not a graph.

On a graph turn the phone draws the verified curve from a ```graph fence. A
model that sketches it with ``*``, ``|`` and ``_`` instead writes rows of
symbols that the phone wraps into broken text. The prompt forbids that sketch;
this removes it after the stream, so the rule holds even when the model ignores
it.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.md_fence_scan import line_fences
from app.services.sketches import PLAIN_FENCE_TAGS, could_be_plot_row, is_text_plot

_GRAPH_FENCE_TYPES = frozenset({"function", "vertical", "number_line", "trajectory", "inequality"})


def strip_text_plots(content: str) -> str:
    """Remove every sketch drawn in characters: a plain fenced block or a run of rows."""
    lines = content.split("\n")
    owners = line_fences(content)
    kept: list[str] = []
    run: list[str] = []

    def flush_run() -> None:
        if not is_text_plot(run):
            kept.extend(run)
        run.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        fence = owners[i]
        if fence is not None:
            flush_run()
            close = i
            while close + 1 < len(lines) and owners[close + 1] is fence:
                close += 1
            block = lines[i : close + 1]
            body = [row for row in block[1 : -1 if fence.closed else None] if row.strip()]
            if not (fence.lang in PLAIN_FENCE_TAGS and is_text_plot(body)):
                kept.extend(block)
            i = close + 1
            continue
        if could_be_plot_row(line):
            run.append(line)
        else:
            flush_run()
            kept.append(line)
        i += 1
    flush_run()
    if len(kept) == len(lines):
        return content
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def is_curve_fence(spec: Any) -> bool:
    """A sampled curve the phone draws in a ```graph, not an answer or a diagram."""
    return isinstance(spec, dict) and spec.get("type") in _GRAPH_FENCE_TYPES


def is_graph_turn(user_text: str, verified: Any) -> bool:
    """A verified curve is attached, or the learner asked to plot maths."""
    fences = [
        getattr(verified, "canonical_fence", None),
        *(getattr(verified, "canonical_fences", None) or ()),
    ]
    if any(is_curve_fence(spec) for spec in fences):
        return True
    from app.modules.math.match.letter_runs import has_viz_command
    from app.modules.math.tools.extract import is_graph_followup
    from app.modules.math.tools.prompt import needs_symbolic_math

    text = user_text or ""
    return is_graph_followup(text) or (has_viz_command(text) and needs_symbolic_math(text))


def asks_for_an_earlier_curve(text: str) -> bool:
    """A graph ask whose own words hold no formula: "can you graph how the balloon's volume
    changes … from the problem earlier?". Its curve can only be the model's reading of the
    chat, so no user line matches the call; a message with a formula of its own is
    matched against that formula instead. (Here, beside the graph ask, so the tool check
    reaches nothing above it.)"""
    from app.modules.math.tool_check import holds_no_formula

    return is_graph_turn(text, None) and holds_no_formula(text)


def strip_text_plots_on_graph_turn(content: str, user_text: str, verified: Any) -> str:
    """Only on a graph turn: an ASCII drawing the learner asked for is left alone."""
    if not content or not is_graph_turn(user_text, verified):
        return content
    return strip_text_plots(content)
