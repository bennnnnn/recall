"""Real field diagrams the server writes, committed for the phone to parse and draw.

`docs/fixtures/field_scenes.json` is the server's own ```simulation fences for the owner's
field questions (2026-11-16) and a few more; the phone reads every one as the app reads a
fence (`lib/physics/__tests__/fieldScenes.test.ts`). This test holds the dump to what the
server writes today. A change in the tracing is a regenerated dump:

    UPDATE_FIELD_FIXTURE=1 uv run pytest app/tests/modules/physics/test_field_scene_fixture.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.modules.physics.field_lines.build import field_fences

_REPO = Path(__file__).resolve().parents[6]
FIXTURE = _REPO / "docs" / "fixtures" / "field_scenes.json"

_CASES: list[tuple[str, dict[str, Any]]] = [
    ("a positive charge", {"kind": "field", "part": "a", "charges": [{"sign": "+"}]}),
    ("a negative charge", {"kind": "field", "part": "b", "charges": [{"sign": "-"}]}),
    (
        "a positive and a negative charge",
        {"kind": "field", "part": "a", "charges": [{"sign": "+"}, {"sign": "-"}]},
    ),
    (
        "two negative charges",
        {"kind": "field", "part": "b", "charges": [{"sign": "-"}, {"sign": "-"}]},
    ),
    (
        "between two oppositely charged flat metal plates",
        {"kind": "field", "part": "c", "plates": {"positive": "top"}},
    ),
    (
        "a charge of +2q and a charge of -q",
        {"kind": "field", "charges": [{"sign": "+", "amount": "2q"}, {"sign": "-", "amount": "q"}]},
    ),
    (
        "charges of +4 μC and +1 μC",
        {
            "kind": "field",
            "charges": [{"sign": "+", "amount": "4 μC"}, {"sign": "+", "amount": "1 μC"}],
        },
    ),
]


def _scenes() -> list[dict[str, str]]:
    scenes = []
    for question, description in _CASES:
        (fence,) = field_fences([json.dumps(description)], [f"Draw the field around {question}."])
        scenes.append({"question": question, "fence": fence})
    return scenes


def test_the_dump_is_what_the_server_writes() -> None:
    written = _scenes()
    if os.environ.get("UPDATE_FIELD_FIXTURE"):
        FIXTURE.write_text(json.dumps({"scenes": written}, indent=1, ensure_ascii=False) + "\n")
    assert json.loads(FIXTURE.read_text())["scenes"] == written
