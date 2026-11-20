"""A chart of the answers the reply before gave: "can you show this on a graph?".

After "find the pressure at a depth of 10 m, 100 m, 1000 m and 2000 m", the model charted
its four answers and the chart was taken out: its values were the reply's, never the user's,
and only the user's own numbers ground a chart (``grounding``; Grade 8 round, t29). The
reply's answer cards are what the student was shown, so a chart of them holds when it is
exactly them: one point per card, in the cards' order, each value a card's number, and each
label a phrase of the question in the same order ("10 m", "100 m", ...). Anything else
draws nothing.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

from app.modules.charts.build import chart_fence
from app.modules.charts.grounding import grounded_title, number_value
from app.modules.charts.request import ChartRequest
from app.services.latex_markup import without_markup
from app.services.md_fence_scan import iter_closed_fences
from app.services.number_text import fold_scientific

# The first number of a card's value, as the markup-free text writes it ("1.03e5 Pa").
_NUMBER = re.compile("[-\u2212]?" r"\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
_SPACES = re.compile(r"\s+")


def answer_values(reply: str) -> list[float]:
    """The number on each of the reply's ```answer cards, in order; none when one card has
    no number (a sentence answer), so a chart is never of some of them."""
    values: list[float] = []
    for _start, _end, body in iter_closed_fences(reply, "answer"):
        lines = [ln for ln in body.splitlines() if ln.strip() and ":" not in ln.split()[0]]
        text = fold_scientific(without_markup(" ".join(lines))).replace("\\,", " ")
        found = _NUMBER.search(text.replace(",", ""))
        if found is None:
            return []
        values.append(float(found.group().replace("\u2212", "-")))
    return values


_TOKEN = re.compile(r"\d+(?:\.\d+)?|[^\W\d_]+|\S")


def _whole(label: str) -> re.Pattern[str] | None:
    """``label`` as the question may write it, spaces between its parts or none ("10 m" as
    "10m"), and whole: a number not inside a longer one ("10" in "10 m", not in "100"), a
    word not inside a longer word ("a" never in "area")."""
    tokens = _TOKEN.findall(label.lower())
    if not tokens or len("".join(tokens)) < 2:
        return None
    edge = "0-9." if tokens[0][0].isdigit() else r"^\W\d_"
    tail = "0-9." if tokens[-1][-1].isdigit() else r"^\W\d_"
    body = r"\s*".join(re.escape(token) for token in tokens)
    return re.compile(rf"(?<![{edge}]){body}(?![{tail}])")


def _in_order(labels: Sequence[str], question: str) -> bool:
    """Each label is written in the question, after the one before it."""
    text = question.lower()
    at = 0
    for label in labels:
        pattern = _whole(label)
        found = pattern.search(text, at) if pattern is not None else None
        if found is None:
            return False
        at = found.end()
    return True


def chart_of_answers(request: ChartRequest, question: str, answers: Sequence[float]) -> str | None:
    """The fence for a bar or line chart of exactly the cards' values, labelled from the
    question in its order; None otherwise."""
    if request.kind not in {"bar", "line"} or len(answers) < 2:
        return None
    values = [number_value(point.value) for point in request.points]
    if len(values) != len(answers) or any(
        value is None or not math.isclose(value, answer, rel_tol=1e-9)
        for value, answer in zip(values, answers, strict=True)
    ):
        return None
    labels = [_SPACES.sub(" ", point.label).strip() for point in request.points]
    if not _in_order(labels, question):
        return None
    pairs = [(label, answer) for label, answer in zip(labels, answers, strict=True)]
    return chart_fence(
        request.kind,
        pairs=pairs,
        label_title=grounded_title(request.label_name, question),
        value_title=None,
    )
