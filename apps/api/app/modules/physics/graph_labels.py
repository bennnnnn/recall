"""A motion graph's title and axes, written in the textbook's symbols.

The phone draws a graph's title and axis names as the server writes them; only a scene's
title has a key the phone translates (``schemas/scene_titles``). Written in English
("Velocity vs. Time", "Time (s)"), they stood in English under a reply in any language. A
quantity's symbol and its unit read the same in every language: "v-t" (with an en dash),
"t (s)", "v (m/s)". One table for every motion graph, so a speed graph and a velocity graph
name their axes as their own wherever they are drawn.
"""

from __future__ import annotations

from typing import Literal

Quantity = Literal["displacement", "distance", "velocity", "speed", "acceleration", "oscillation"]

# The textbook letters: s for a displacement, d for a distance, v for a velocity and |v| for
# a speed (its size: a speed graph is never a velocity graph), a, and x for an oscillator's
# displacement from its rest position.
SYMBOLS: dict[Quantity, str] = {
    "displacement": "s",
    "distance": "d",
    "velocity": "v",
    "speed": "|v|",
    "acceleration": "a",
    "oscillation": "x",
}
TIME = "t"
# A graph's name as a textbook writes it, "v-t graph": the two symbols joined by an en dash.
_AGAINST = chr(0x2013)


def axis_label(symbol: str, unit: str) -> str:
    """An axis as its quantity's symbol and unit: ``v (m/s)``."""
    return f"{symbol} ({unit})"


def graph_title(symbol: str) -> str:
    """A graph against time by its quantity's symbol: ``v`` gives v, an en dash, t."""
    return f"{symbol}{_AGAINST}{TIME}"
