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

_FENCE = re.compile(r"^\s*```\s*([A-Za-z0-9_+-]*)\s*$")
# A plain block may hold a sketch; a tagged one (graph, math, python) never does.
_PLAIN_FENCE_TAGS = frozenset({"", "text", "txt", "plaintext", "ascii"})
_WORD = re.compile(r"[A-Za-z]{3,}")
# ``12|``, ``  |``, ``0+--``: the y-axis at the start of a row.
_Y_AXIS = re.compile(r"^\s*[-+]?\d*(?:\.\d+)?\s*[|+](?:\s|$|[-_*•●o/\\])")
_X_AXIS = re.compile(r"[-_]{5,}")
_MARK = re.compile(r"(?<![\w*])[*•●](?![\w*])|(?<![\w])o(?![\w])|[/\\]")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_GRAPH_FENCE_TYPES = frozenset({"function", "vertical", "number_line", "trajectory", "inequality"})


def _could_be_plot_row(line: str) -> bool:
    """Axis rows, point rows and tick labels: no math, at most a couple of words."""
    return bool(line.strip()) and "$" not in line and len(_WORD.findall(line)) <= 2


def _is_text_plot(rows: list[str]) -> bool:
    if len(rows) < 3 or any(_TABLE_RULE.match(row) for row in rows):
        return False
    axis = sum(bool(_Y_AXIS.match(row)) for row in rows) >= 3 or any(
        _X_AXIS.search(row) for row in rows
    )
    marked = sum(bool(_MARK.search(row)) for row in rows) >= 2
    return axis and marked


def strip_text_plots(content: str) -> str:
    """Remove every sketch drawn in characters: a plain fenced block or a run of rows."""
    lines = content.split("\n")
    kept: list[str] = []
    run: list[str] = []

    def flush_run() -> None:
        if not _is_text_plot(run):
            kept.extend(run)
        run.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        fence = _FENCE.match(line)
        if fence is not None:
            flush_run()
            close = next(
                (j for j in range(i + 1, len(lines)) if _FENCE.match(lines[j])), len(lines) - 1
            )
            block = lines[i : close + 1]
            body = [row for row in lines[i + 1 : close] if row.strip()]
            if not (fence.group(1).lower() in _PLAIN_FENCE_TAGS and _is_text_plot(body)):
                kept.extend(block)
            i = close + 1
            continue
        if _could_be_plot_row(line):
            run.append(line)
        else:
            flush_run()
            kept.append(line)
        i += 1
    flush_run()
    if len(kept) == len(lines):
        return content
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def is_graph_turn(user_text: str, verified: Any) -> bool:
    """A verified curve is attached, or the learner asked to plot maths."""
    fences = [
        getattr(verified, "canonical_fence", None),
        *(getattr(verified, "canonical_fences", None) or ()),
    ]
    if any(isinstance(spec, dict) and spec.get("type") in _GRAPH_FENCE_TYPES for spec in fences):
        return True
    from app.modules.math.match.scan import has_viz_command
    from app.modules.math.tools.extract import is_graph_followup
    from app.modules.math.tools.prompt import needs_symbolic_math

    text = user_text or ""
    return is_graph_followup(text) or (has_viz_command(text) and needs_symbolic_math(text))


def strip_text_plots_on_graph_turn(content: str, user_text: str, verified: Any) -> str:
    """Only on a graph turn: an ASCII drawing the learner asked for is left alone."""
    if not content or not is_graph_turn(user_text, verified):
        return content
    return strip_text_plots(content)
