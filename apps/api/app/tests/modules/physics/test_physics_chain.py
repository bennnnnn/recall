"""Every quantity a question asks for is answered by a catalog law, laws chained.

Live on 2026-11-03, two asks or two steps fell to the model unchecked: "how high … and how
long", "the deceleration and how far". The answers below are worked by hand.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.chain_solve import solve_chain
from app.modules.physics.prompt import solve_physics_request

_SETTINGS = Settings()


def _parts(text: str) -> list[str]:
    outcome, block = solve_physics_request(text, _SETTINGS, None)
    assert outcome == "verified" and block is not None
    return [part.answer for part in block.physics_parts]


@pytest.mark.parametrize(
    ("text", "answers"),
    [
        # h = 15²/(2·9.81) = 11.47 m; t = 2·15/9.81 = 3.06 s.
        (
            "a ball is thrown straight up at 15 m/s. how high does it go and how long till it "
            "comes back down",
            ["11.5 m", "3.06 s"],
        ),
        # 72 km/h = 20 m/s; a = (0 - 20)/4 = -5 m/s²; s = ½(20 + 0)·4 = 40 m.
        (
            "car going 72 km/h slams the brakes and stops in 4 s. whats the deceleration and "
            "how far does it go before stopping",
            ["-5 m/s²", "40 m"],
        ),
        # p = 2·3 = 6 kg·m/s; KE = ½·2·3² = 9 J.
        (
            "A 2 kg ball moves at 3 m/s. Find its momentum and its kinetic energy.",
            ["6 kg·m/s", "9 J"],
        ),
        # I = 9/12 = 0.75 A; P = 9²/12 = 6.75 W.
        (
            "A 12 ohm resistor is connected to a 9 V battery. Find the current and the power "
            "dissipated.",
            ["0.75 A", "6.75 W"],
        ),
        # h = 20²/(2·9.81) = 20.4 m; t_top = 20/9.81 = 2.04 s; t = 4.08 s.
        (
            "A ball is thrown straight up at 20 m/s. Find (a) the maximum height (b) the time "
            "to reach the top (c) the total time in the air.",
            ["20.4 m", "2.04 s", "4.08 s"],
        ),
    ],
)
def test_every_ask_gets_its_own_verified_part(text: str, answers: list[str]) -> None:
    assert _parts(text) == answers


def test_one_ask_a_plain_law_and_a_stopping_one_both_name_takes_the_stopping_one() -> None:
    # d = vt and s = ½(u + v)t are named alike; only the second reads "stops in" (v = 0).
    outcome, block = solve_physics_request(
        "a car going 72 km/h stops in 4 s. how far does it travel while stopping", _SETTINGS, None
    )
    assert outcome == "verified" and block is not None
    assert block.canonical_answer == "40 m"


@pytest.mark.parametrize(
    "text",
    [
        # A part that changes the situation is no question read alone.
        "A 2 kg ball moves at 3 m/s. Find its momentum and its kinetic energy if the speed doubles.",
        # A stated drag law is the drag law's fall, not free fall.
        "A ball is dropped from 20 m. F = -kv. How high and how long until it hits the ground?",
        # An angle named and not stated: W = Fd is the parallel case.
        "How much work is done by a 10 N force at an angle over 4 m, and what power in 2 s?",
        # A network of resistors is another law's; one resistor of it is the wrong circuit.
        "A 6 Ω resistor is in parallel with an identical one across 12 V. Find the current and "
        "the power.",
        # A stated force the chain never uses: the throw is not free fall alone.
        "A ball is thrown straight up at 15 m/s by a 30 N push. How high does it go and how long "
        "till it comes back down?",
        # The final speed and the kinetic energy with no mass stated.
        "A car accelerates from rest at 2 m/s^2 for 5 s. Find its final speed and its kinetic "
        "energy.",
    ],
)
def test_the_chain_declines_what_it_cannot_answer_whole(text: str) -> None:
    assert solve_chain(text, _SETTINGS) is None
