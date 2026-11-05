"""How a verified answer reads: symbols a student reads right, long times in a counted unit,
and physics on its own switch."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.physics.answer_checks import _readable_time
from app.modules.physics.catalog import formula_spec
from app.modules.physics.prompt import build_physics_augmentation
from app.modules.physics.solvers.results import QuantityResult, solved


@pytest.mark.parametrize(
    ("seconds", "note"),
    [
        (5545.0, "92.4 min"),  # a 400 km orbit
        (7200.0, "2 h"),
        (3 * 86400.0, "3 days"),
        (3.156e7 * 3, "3 years"),
    ],
)
def test_a_long_time_in_seconds_also_reads_in_a_counted_unit(seconds: float, note: str) -> None:
    shown = _readable_time(solved(QuantityResult("T", seconds, "s"), answer=""))
    assert shown.quantities[0].detail == note
    assert shown.quantities[0].unit == "s"


@pytest.mark.parametrize(
    "quantity",
    [
        QuantityResult("t", 45.0, "s"),  # short: seconds are the counted unit
        QuantityResult("t", 2.0, "h"),  # already in hours
        QuantityResult("t", 5545.0, "s", detail="one orbit"),  # a note of its own stays
    ],
)
def test_other_times_are_left_as_written(quantity: QuantityResult) -> None:
    assert _readable_time(solved(quantity, answer="")).quantities[0] == quantity


def test_lens_distances_are_d_o_and_d_i_never_speeds() -> None:
    for operation in ("image_distance", "magnification_distances", "mirror_image_from_radius"):
        spec = formula_spec(operation)
        assert spec is not None
        symbols = {variable.symbol for variable in spec.variables}
        assert not symbols & {"u", "v"}
        assert "\\frac{1}{u}" not in (spec.base_latex or "")
    lens = formula_spec("image_distance")
    assert lens is not None and lens.result_symbol == "d_i"


async def test_physics_has_its_own_switch() -> None:
    text = "A 2 kg ball moves at 3 m/s. What is its kinetic energy?"
    off = Settings(math_tools_enabled=True, physics_enabled=False)
    assert await build_physics_augmentation(text, off) == (None, None, False)
    on = Settings(math_tools_enabled=False, physics_enabled=True)
    _prompt, verified, _failed = await build_physics_augmentation(text, on)
    assert verified is not None
