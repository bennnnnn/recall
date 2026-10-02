"""Physics replies the server writes are the replies the phone and the web read.

`docs/fixtures/physics_replies.json` holds real direct replies and the plain
answer each one carries. This test proves the server still writes exactly
those; the mobile (`lib/__tests__/physicsReplyContract.test.ts`) and web
(`src/lib/physicsReplyContract.test.ts`) tests read the same file and prove
each client shows the answer as text a person can read. To accept an intended
change to the replies, regenerate the file:

    UPDATE_PHYSICS_FIXTURE=1 uv run pytest app/tests/modules/physics/test_physics_reply_contract.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Settings
from app.modules.physics import build_verified_physics_block, extract_physics_intent
from app.modules.physics.direct import maybe_direct_physics_reply

FIXTURE = Path(__file__).resolve().parents[6] / "docs" / "fixtures" / "physics_replies.json"
_SETTINGS = Settings(math_tools_enabled=True)

# One of each answer shape: scientific notation with a note, an angle pair, a
# unit symbol, a direction note, a converted unit, and a multipart projectile.
QUESTIONS = {
    "photon_energy": "Find the energy of a photon of wavelength 500 nm.",
    "launch_angles": "At what angle must a projectile be launched at 20 m/s to land 30 m away?",
    "parallel_resistance": "Find the total resistance of 4 ohm, 6 ohm and 12 ohm resistors in parallel.",
    "rebound_impulse": "A 0.2 kg ball hits a wall at 10 m/s and rebounds at 8 m/s. Find the impulse.",
    "heater_energy": "A 2 kW heater runs for 3 hours. How much energy does it use in kWh?",
    "projectile_parts": (
        "A projectile is launched at 20 m/s at 30 degrees. "
        "Find the time of flight, the maximum height and the range."
    ),
}


def _entry(question: str) -> dict[str, str]:
    intent = extract_physics_intent(question)
    assert intent is not None, question
    verified = build_verified_physics_block(intent, _SETTINGS)
    assert verified is not None and verified.canonical_answer is not None, question
    reply = maybe_direct_physics_reply(verified, question)
    assert reply is not None, question
    return {"question": question, "answer": verified.canonical_answer, "reply": reply}


def _current() -> dict[str, Any]:
    return {"replies": {name: _entry(question) for name, question in QUESTIONS.items()}}


def _stored() -> dict[str, Any]:
    if os.environ.get("UPDATE_PHYSICS_FIXTURE"):
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(
            json.dumps(_current(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", list(QUESTIONS))
def test_the_server_still_writes_the_stored_reply(name: str) -> None:
    stored = _stored()["replies"][name]
    assert stored == _entry(QUESTIONS[name])


def test_every_reply_carries_a_typeset_answer_card() -> None:
    for entry in _stored()["replies"].values():
        assert "```answer\n" in entry["reply"]
        card = entry["reply"].split("```answer\n", 1)[1].split("\n```", 1)[0]
        assert "\\" in card, "the card is LaTeX"
        assert "\\" not in entry["answer"], "the plain answer is text"
