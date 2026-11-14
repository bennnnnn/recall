"""Real ```simulation scenes the server writes, committed for the phone to parse.

The phone's scene tests read hand-written fixtures, so nothing in CI held its parsers to what
the server actually sends (GFX-04, 2026-11-13 STEM audit: 219 real fences parsed then, held by
no test). `docs/fixtures/simulation_scenes.json` is a dump of the solver's own scenes for the
physics STEM corpus, a few of each scene type; the phone parses every one
(`lib/physics/__tests__/serverScenes.test.ts`). This test holds the dump to the server's
schema and to every scene type the solver draws today. A new type, or a scene that changes
shape, is a regenerated dump:

    UPDATE_SCENE_FIXTURE=1 uv run pytest app/tests/services/test_simulation_scene_fixture.py
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.modules.physics.fence import solver_cards
from app.modules.physics.schemas.simulation import SimulationBlockSpec

_REPO = Path(__file__).resolve().parents[5]
FIXTURE = _REPO / "docs" / "fixtures" / "simulation_scenes.json"
_CORPUS = Path(__file__).resolve().parents[1] / "behavior" / "stem_corpus" / "physics"
_SETTINGS = Settings(math_tools_enabled=True)
# Enough of each type to vary its shape (a circuit's networks, a free body's forces), small
# enough to commit: about 90 scenes, 230 KB.
_PER_TYPE = 8
_OPEN = "```simulation\n"


def _body(card: str) -> str:
    return card[len(_OPEN) :].rsplit("\n```", 1)[0]


def _server_scenes() -> list[dict[str, Any]]:
    """The solver's scenes for the corpus's questions, in corpus order, a few of each type."""
    scenes: list[dict[str, Any]] = []
    per_type: Counter[str] = Counter()
    for path in sorted(_CORPUS.glob("*.json")):
        for item in json.loads(path.read_text()):
            question = item.get("prompt")
            intent = extract_physics_intent(question) if question else None
            verified = build_verified_physics_block(intent, _SETTINGS) if intent else None
            if verified is None:
                continue
            for card in solver_cards(verified):
                if not card.startswith(_OPEN):
                    continue
                kind = str(json.loads(_body(card))["type"])
                if per_type[kind] < _PER_TYPE:
                    per_type[kind] += 1
                    scenes.append({"question": question, "type": kind, "fence": card})
    return scenes


@pytest.fixture(scope="module")
def dump() -> list[dict[str, Any]]:
    if os.environ.get("UPDATE_SCENE_FIXTURE"):
        FIXTURE.write_text(
            json.dumps({"scenes": _server_scenes()}, indent=1, ensure_ascii=False) + "\n"
        )
    scenes: list[dict[str, Any]] = json.loads(FIXTURE.read_text())["scenes"]
    return scenes


def test_every_dumped_scene_is_one_the_server_writes(dump: list[dict[str, Any]]) -> None:
    for scene in dump:
        assert scene["fence"].startswith(_OPEN) and scene["fence"].endswith("\n```")
        spec = SimulationBlockSpec.model_validate(json.loads(_body(scene["fence"])))
        assert spec.type == scene["type"], scene["question"]


def test_the_dump_covers_every_scene_type_the_solver_draws(dump: list[dict[str, Any]]) -> None:
    drawn = {scene["type"] for scene in _server_scenes()}
    dumped = {scene["type"] for scene in dump}
    assert drawn <= dumped, (
        f"the solver draws {sorted(drawn - dumped)}, which the phone's dump lacks: "
        "UPDATE_SCENE_FIXTURE=1 uv run pytest app/tests/services/test_simulation_scene_fixture.py"
    )
