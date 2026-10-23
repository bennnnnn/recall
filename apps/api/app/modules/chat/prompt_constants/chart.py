"""A numeric chart turn: what reads as one, and the one chart contract.

The phone draws a ```chart fence with Vega-Lite whose data is written inline
(``apps/mobile/lib/chartSpec.ts``); anything else shows the chart's data as a table
instead. ``CHART_FORMAT_HINT`` names only the shapes it draws. Their examples are
``chart_shapes.json``, and the phone's tests draw every one of them
(``apps/mobile/lib/__tests__/chartShapes.test.ts``), so the hint cannot promise a
shape the phone leaves blank. A curve y = f(x) is not one of them: the server samples
it with SymPy (``modules/math/chart_formula.py``).
"""

import json
import re
from pathlib import Path

from app.services.diagram_kinds import names_diagram_kind, names_idea_curve

CHART_SHAPES: dict[str, dict[str, object]] = json.loads(
    Path(__file__).with_name("chart_shapes.json").read_text(encoding="utf-8")
)

_CHART_KINDS = ("bar", "line", "pie", "area", "scatter", "donut", "dot", "box")

_CHART_TURN = re.compile(
    r"(?:"
    r"\b(?:bar|line|pie|area|scatter|donut)\s+charts?\s+(?:of|for|with|from|using)\b|"
    r"\bcharts?\s+(?:of|for|my)\b|"
    r"\bhistograms?\b|"
    r"\bvega(?:-lite)?\b|"
    r"```(?:chart|vega|vega-lite|plot)\b|"
    r"\b(?:make|draw|show|create|render|plot)\s+a\s+"
    r"(?:bar\s+|line\s+|pie\s+|area\s+)?charts?\b"
    r")",
    re.IGNORECASE,
)
# A plot of data named by its kind ("scatter plot", "bar graph", "box-and-whisker plot"),
# asked for: "make a bar graph", "a scatterplot of …". Not "my bar graph homework", and
# not "a box of plots" or "plot the boxes".
_PLOT_KIND = (
    r"(?:(?:scatter|dot|bar|pie|donut|line|area)\s*(?:plots?|graphs?)"
    r"|box(?:[\s-]+and[\s-]+whiskers?)?[\s-]*(?:plots?|charts?|graphs?))\b"
)
_PLOT_REQUEST = re.compile(
    r"\b(?:make|draw|create|plot|show|give|build|render|generate)\b[^.?!\n]{0,40}?\b"
    + _PLOT_KIND
    + r"|\b"
    + _PLOT_KIND
    + r"\s+(?:of|for|with|from|showing)\b",
    re.IGNORECASE,
)
# The verb that asks for a drawing; what follows it may name a curve of an idea.
_DRAW_VERB = re.compile(
    r"\b(?:make|draw|create|plot|show|give|build|render|generate|sketch)\b(?:\s+(?:me|us)\b)?",
    re.IGNORECASE,
)
# "a line graph of my sales" is a chart; "the line graph of y = 2x + 1" is a curve.
_LINE_PLOT = re.compile(r"\b(?:line|area)\s*(?:graphs?|plots?)\b", re.IGNORECASE)
_CURVE = re.compile(r"\bf\s*\(\s*x\s*\)|\by\s*=\s*[^,;\n]*?x", re.IGNORECASE)
_DEFINITION = re.compile(
    r"\bwhat(?:\s+is|'s|\s+are)\s+(?:a\s+|an\s+)?"
    rf"(?:(?:{'|'.join(_CHART_KINDS)})\s*)?(?:charts?|plots?|graphs?)\b",
    re.IGNORECASE,
)


def _shape_lines() -> str:
    return "\n".join(
        f"{name}:\n```chart\n{json.dumps(spec, separators=(',', ':'), ensure_ascii=False)}\n```"
        for name, spec in CHART_SHAPES.items()
    )


CHART_FORMAT_HINT = (
    "This turn is a numeric chart. Recall renders Vega-Lite in the bubble — "
    "you CAN draw this chart. NEVER say you cannot draw / cannot literally "
    "draw a chart. NEVER substitute a markdown table, mermaid, or ASCII bars.\n"
    "Lead with a ```chart fence of Vega-Lite JSON. At most one short sentence "
    "before the fence. No joke setup. No leftover bare numbers and no "
    "```answer / ```result fence.\n"
    "If they gave numbers, use those as data.values in that order. "
    "If they asked for an example or a generic chart with no series, a short "
    "labelled sample is fine — say it is sample data in that one sentence. "
    "If they asked to chart their real/my data and gave no numbers, ask ONE "
    "question for the values. Do not invent a sample and treat that as the answer.\n"
    "If they also asked for a statistic or explanation, put that after the fence. "
    "Do not stop immediately after the chart unless they only asked for the drawing.\n"
    "The app draws only these shapes; use the one asked for and keep its structure:\n"
    '- bar: named categories (months, items) on y with "sort": null (horizontal bars) '
    "so labels stay visible; grouped series dodge with yOffset.\n"
    '- line or area: x in data order ("sort": null on a named x), one line per series '
    "by color.\n"
    "- scatter: mark point, x and y quantitative. A best-fit or trend line is a second "
    "layer with the regression transform: the app fits it to the data, so never compute "
    "or write the line's points yourself.\n"
    '- histogram: the raw values as data.values, x with "bin", y '
    '{"aggregate": "count"}. Never pre-bin the values, never "bin": "binned".\n'
    "- pie: mark arc, theta is the number, color is the category.\n"
    "- box plot: mark boxplot over the raw values as data.values, one row per value; a "
    "category on x gives one box per group, no x gives one box. Never compute the "
    "quartiles or whiskers yourself.\n"
    "Every chart: first key "
    '"$schema": "https://vega.github.io/schema/vega-lite/v5.json"; every value inline '
    "in data.values (no url, no data.sequence, no column computed from a formula); "
    "no tooltip; one complete JSON object with nothing after its closing brace; never "
    "Chart.js or another format.\n"
    "A curve y = f(x) is not data: never sample or compute its points. Write it as "
    '```chart {"type":"function","series":[{"name":"y = sin(x)","fn":"sin(x)"}],'
    '"domain":[0,6.2832]} (one or two series) and Recall draws it from the formula.\n'
    f"{_shape_lines()}"
)


def _is_chart_definition(cleaned: str) -> bool:
    return bool(_DEFINITION.search(cleaned))


def _chart_request_negated(cleaned: str) -> bool:
    lower = cleaned.lower()
    if "chart" not in lower:
        return False
    for neg in ("do not", "don't", "dont", "never", "without"):
        start = 0
        while True:
            idx = lower.find(neg, start)
            if idx < 0:
                break
            window = lower[idx : idx + 80]
            if "chart" in window and any(
                verb in window for verb in ("make", "draw", "create", "render", "plot")
            ):
                return True
            start = idx + len(neg)
    return False


def is_chart_question(text: str) -> bool:
    """True when the user asked to draw a numeric chart (Vega), not define one."""
    cleaned = text.strip()
    if not cleaned:
        return False
    if _is_chart_definition(cleaned) or _chart_request_negated(cleaned):
        return False
    # "An org chart" or "a Gantt chart" is a Mermaid diagram, not numbers.
    if names_diagram_kind(cleaned):
        return False
    if _CHART_TURN.search(cleaned):
        return True
    # "Draw the learning curve": an idea's curve, as a chart with sample data.
    asked = _DRAW_VERB.search(cleaned)
    if asked is not None and names_idea_curve(cleaned[asked.end() :]):
        return True
    if not _PLOT_REQUEST.search(cleaned):
        return False
    return not (_LINE_PLOT.search(cleaned) and _CURVE.search(cleaned))


def chart_names_no_curve(text: str) -> bool:
    """A chart request in which maths reads no curve y = f(x).

    The user's own numbers ("a scatter plot of x = 1, 2, 3 and y = …"), or a formula
    maths cannot read: either way there is nothing to verify, so the turn is the
    chart contract's (a formula chart is sampled after the reply). A curve maths reads
    ("line chart of y = x^2") stays maths'. Runs where subjects are read, off the loop.
    """
    if not is_chart_question(text):
        return False
    from app.modules.math.tools.extract import extract_math_intent

    intent = extract_math_intent(text)
    return intent is None or (intent.kind == "graph" and not intent.expr)
