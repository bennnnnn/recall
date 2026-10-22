"""Diagrams the app draws itself as a ```mermaid card, by the names people give them.

Images reads this so "draw a decision tree" is never an AI picture, whose labels come
out garbled; chat reads it to lead the reply with the right Mermaid diagram, and so an
org chart is never mistaken for a numeric chart.
"""

from __future__ import annotations

import re
from itertools import pairwise

# Named by two words, the second of which alone can be a fair picture ("draw a tree").
DIAGRAM_KIND_PAIRS = frozenset(
    {
        ("decision", "tree"),
        ("family", "tree"),
        ("org", "chart"),
        ("organization", "chart"),
        ("organizational", "chart"),
        ("process", "map"),
        ("mind", "map"),
        ("concept", "map"),
        ("journey", "map"),
        ("state", "machine"),
        ("state", "diagram"),
        ("class", "diagram"),
        ("er", "diagram"),
        ("entity", "relationship"),
        ("gantt", "chart"),
    },
)
# Named by one word.
DIAGRAM_KIND_WORDS = frozenset({"mindmap", "mindmaps", "erd"})

_WORD = re.compile(r"[a-z]+")


def names_diagram_kind(text: str) -> bool:
    """True when the text names one of these diagrams ("a state-machine", "an ERD")."""
    words = _WORD.findall(text.lower())
    return any(word in DIAGRAM_KIND_WORDS for word in words) or any(
        pair in DIAGRAM_KIND_PAIRS for pair in pairwise(words)
    )
