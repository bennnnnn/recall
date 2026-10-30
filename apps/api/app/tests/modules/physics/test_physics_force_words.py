"""A word before "force" is still the force asked for (2026-10-30, a grade 7 physics
book: "How much external force is required…" got no verified answer)."""

import pytest

from app.core.config import Settings
from app.modules.physics.prompt import solve_physics_request


@pytest.mark.parametrize(
    "question",
    [
        "4) How much external force is required to accelerate a 1500 kg car at the rate of "
        "6m/s2\n?",
        "How much external force is needed to accelerate a 1500 kg car at 6 m/s^2?",
        "What applied force accelerates a 1500 kg car at 6 m/s^2?",
        "Find the resultant force on a 1500 kg car accelerating at 6 m/s^2.",
    ],
)
def test_a_described_force_is_the_force_asked_for(question: str) -> None:
    _, block = solve_physics_request(question, Settings(math_tools_enabled=True), None)
    assert block is not None and block.display_answer == r"9000\,\mathrm{N}"
