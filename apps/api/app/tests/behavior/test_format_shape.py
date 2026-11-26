"""The layout judge the format eval uses (``format_shape``), on the owner's example."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.tests.behavior.format_shape import STRUCTURED, misses, shape_of

# The owner's shape for "what are types of science" (2026-11-26).
_TARGET = """Science is the study of the world, usually split into three main groups.

## Types of Sciences

1. **Natural science** — studies the physical and living world.
   - Chemistry
   - Biology
   - Physics
2. **Social science** — studies people and societies.
   - History
   - Economics
3. **Formal science** — studies abstract systems.
   - Mathematics
   - Logic
"""

# What the app wrote on 2026-11-26: no title, members in a sentence.
_TODAY = """There are three main types of science, with many branches under each.

- 🧪 **Natural sciences**: study the physical world, including physics and chemistry.
- 🧠 **Social sciences**: study human behaviour, including psychology and economics.
- 📐 **Formal sciences**: study abstract systems, including mathematics and logic.
"""


def test_the_owner_s_example_is_the_shape_wanted() -> None:
    assert misses("overview", shape_of(_TARGET)) == []


def test_today_s_reply_lacks_a_title_and_nested_members() -> None:
    assert misses("overview", shape_of(_TODAY)) == ["no title", "no nested members"]


@pytest.mark.parametrize(
    ("kind", "reply", "lacks"),
    [
        ("fact", "Tokyo is the capital of **Japan**.", []),
        (
            "fact",
            "## Capital\n\nTokyo is the capital of Japan.",
            ["heading on a fact", "fact not bold"],
        ),
        ("casual", "Congrats on the new job! How was your first day?", []),
        ("casual", "Congrats!\n\n- Celebrate\n- Rest", ["list in conversation"]),
        ("maths", "**Given**\n\n```answer\nx = 4\n```", []),
        ("maths", "x is 4.", ["no answer card"]),
        ("howto", "You need beans and water.\n\n```steps\n1. **Grind**\nFine.\n```", []),
    ],
)
def test_each_kind_is_held_to_its_own_shape(kind: str, reply: str, lacks: list[str]) -> None:
    assert misses(kind, shape_of(reply)) == lacks


def test_code_and_card_fences_are_not_read_as_layout() -> None:
    reply = "Here it is.\n\n```python\n# not a heading\n- not a list\n```\n"
    shape = shape_of(reply)
    assert (shape.title, shape.items) == (False, 0)


def test_every_corpus_entry_names_a_known_kind() -> None:
    corpus = json.loads((Path(__file__).parent / "format_corpus.json").read_text())
    kinds = STRUCTURED | {"fact", "casual", "maths"}
    assert {entry["kind"] for entry in corpus} <= kinds
    assert len({entry["id"] for entry in corpus}) == len(corpus)
