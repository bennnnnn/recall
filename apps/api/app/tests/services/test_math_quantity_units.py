"""Physical quantities retain their units in the canonical, visible answer."""

import pytest

from app.core.config import Settings
from app.services import math_tools
from app.services.math_tools.direct import maybe_direct_math_reply


@pytest.mark.parametrize(
    "prompt,answer",
    [
        ("Convert 8 m to cm", r"800\ \mathrm{cm}"),
        ("Convert 5 ft to m", r"1.524\ \mathrm{m}"),
        ("Convert 1 kg to g", r"1000\ \mathrm{g}"),
        ("Convert 2 hours to minutes", r"120\ \mathrm{minutes}"),
        ("Convert 0 C to F", r"32\ \mathrm{°F}"),
        ("Convert 10 m/s to km/h", r"36\ \mathrm{km}/\mathrm{h}"),
        ("Convert 1 J to erg", r"10000000\ \mathrm{erg}"),
        ("Convert 1 m^2 to cm^2", r"10000\ \mathrm{cm}^2"),
        ("Convert .5 m to cm", r"50\ \mathrm{cm}"),
        ("Convert -.5 C to F", r"31.1\ \mathrm{°F}"),
        ("Convert +.5 m to cm", r"50\ \mathrm{cm}"),
        ("Find the volume of a cube side 3 m", r"27\ \mathrm{m}^{3}"),
        ("Find the surface area of a cube side 3 m", r"54\ \mathrm{m}^{2}"),
        ("Find the volume of a rectangular prism 2 by 3 by 4 m", r"24\ \mathrm{m}^{3}"),
        ("Find the surface area of a rectangular prism 2 by 3 by 4 m", r"52\ \mathrm{m}^{2}"),
        ("Find the volume of a cylinder radius 2 m height 3 m", r"37.70\ \mathrm{m}^{3}"),
        ("Find the surface area of a cylinder radius 2 m height 3 m", r"62.83\ \mathrm{m}^{2}"),
        ("Find the volume of a cone radius 3 m height 4 m", r"37.70\ \mathrm{m}^{3}"),
        ("Find the surface area of a cone radius 3 m height 4 m", r"75.40\ \mathrm{m}^{2}"),
        ("Find the volume of a sphere radius 2 m", r"33.51\ \mathrm{m}^{3}"),
        ("Find the surface area of a sphere radius 2 m", r"50.27\ \mathrm{m}^{2}"),
        ("Find the volume of a square pyramid side 6 m height 4 m", r"48\ \mathrm{m}^{3}"),
        ("Find the surface area of a square pyramid side 6 m height 4 m", r"96\ \mathrm{m}^{2}"),
        ("Find the volume of a cube side 3", r"27\ \mathrm{units}^{3}"),
        ("Find the surface area of a cube side 3", r"54\ \mathrm{units}^{2}"),
        ("Find the volume of a cube side 3 feet", r"27\ \mathrm{ft}^{3}"),
        ("Find the volume of a cube side .5 m", r"0.125\ \mathrm{m}^{3}"),
        ("Find the volume of a cube side 0.5 m", r"0.125\ \mathrm{m}^{3}"),
        ("Find the volume of a rectangular prism .5 by 2 by 3 m", r"3\ \mathrm{m}^{3}"),
        ("Find the average speed for 100 m in 20 s.", r"5.0\ \mathrm{m}/\mathrm{s}"),
        ("Find the average speed for 20 s over 100 m.", r"5.0\ \mathrm{m}/\mathrm{s}"),
        ("average speed 120 km in 2 hours", r"60.0\ \mathrm{km}/\mathrm{h}"),
        ("average speed 100 cm in 20 seconds", r"5.0\ \mathrm{cm}/\mathrm{s}"),
        ("average speed 100 feet in 20 minutes", r"5.0\ \mathrm{ft}/\mathrm{min}"),
        ("average speed .5 m in 2 s", r"0.25\ \mathrm{m}/\mathrm{s}"),
        ("average speed 0.5 m in 2 s", r"0.25\ \mathrm{m}/\mathrm{s}"),
        ("average speed 1.5 m in .5 s", r"3.0\ \mathrm{m}/\mathrm{s}"),
        ("average speed +.5 m in 2 s", r"0.25\ \mathrm{m}/\mathrm{s}"),
    ],
)
def test_quantity_answer_retains_the_actual_unit(prompt: str, answer: str) -> None:
    assert math_tools.needs_symbolic_math(prompt)
    intent = math_tools.extract_math_intent(prompt)
    assert intent is not None
    block = math_tools._build_verified_block(intent, Settings())
    assert block is not None and block.canonical_answer == answer
    if prompt == "Convert 8 m to cm":
        assert maybe_direct_math_reply(block, prompt) == f"```answer\n{answer}\n```\n"


@pytest.mark.parametrize(
    "prompt",
    [
        "Find the average speed for 100 kg in 20 s.",
        "Find the average speed for 100 m in 20 bananas.",
        "Find the average speed for 100 m/s in 20 s.",
        "Find the average speed for 100 m in 20 s and then 50 m in 10 s.",
        "Find the average speed for 100 m in 20 s and tell me a joke.",
        "Find the average speed for 100 m in 20 s in km/h.",
        "Find the volume of a cylinder radius 2 cm height 3 m",
        "Find the volume of a cylinder radius 2 bananas height 3 bananas",
        "Find the volume of a cube side 3 m^2",
        "Convert 1 m to cm and 2 kg to g",
        "Convert 1 m to cm then convert 2 kg to g",
        "Convert 1 m and 2 km to cm",
        "Convert 1 m to cm and tell me a joke",
        "average speed .5 m in -.5 s",
        "average speed -.5 m in 2 s",
    ],
)
def test_unsupported_or_compound_measurements_do_not_get_a_partial_answer(prompt: str) -> None:
    assert math_tools.extract_math_intent(prompt) is None
