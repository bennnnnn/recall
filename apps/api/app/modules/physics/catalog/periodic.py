"""Laws read from a periodic motion's period or frequency: a body in simple harmonic
motion, and a wave.

A period is a value the question names as one (``law_binding.labels``), never the time a
trip takes: read as v = d/t, a spring's amplitude and period were a maximum speed of
0.05 m/s for 0.314, and a wave's amplitude and period a wave speed (audit 2026-11-13).
"""

from __future__ import annotations

from app.modules.physics.catalog.spring import MAX_ACCELERATION_ASKS, SHM_CUES
from app.services.law_binding.labels import LABELS
from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

SPECS: tuple[FormulaSpec, ...] = (
    # A body in simple harmonic motion turns at its ends with Aω² = 4π²A/T² = 4π²Af².
    formula(
        "shm_max_acceleration",
        "spring",
        "Simple-harmonic-motion equation",
        "a_{max}",
        base_latex=r"a_{max} = A\omega^2",
        expression="x*omega**2",
        variants=(
            FormulaVariant(
                latex=r"a_{max} = \frac{4\pi^2 A}{T^2}",
                present=frozenset({"period"}),
                expression="4*pi**2*x/period**2",
            ),
            FormulaVariant(
                latex=r"a_{max} = 4\pi^2 A f^2",
                present=frozenset({"freq"}),
                expression="4*pi**2*x*freq**2",
            ),
        ),
        assumptions=("simple harmonic motion",),
        variables=(
            var("x", "A", "meter", words=("amplitude",), needs_words=True),
            var("omega", r"\omega", "radian / second"),
            var("period", "T", "second", words=LABELS["period"], needs_words=True),
            var("freq", "f", "hertz"),
        ),
        binding=Binding(
            asks=MAX_ACCELERATION_ASKS,
            result=("meter / second ** 2",),
            inputs=tuple(frozenset({"x", rate}) for rate in ("omega", "period", "freq")),
            cues=SHM_CUES,
            nonnegative=True,
        ),
    ),
    # A wave moves one wavelength each period: v = λ/T. Read as v = d/t, "a wavelength of
    # 200 km and a period of 15 minutes" had the right number from the wrong law, and "an
    # amplitude of 0.1 m and a period of 2 s" a wave speed it does not have (audit 2026-11-13).
    formula(
        "wave_speed_from_period",
        "waves",
        "Wave equation",
        "v",
        base_latex=r"v = \frac{\lambda}{T}",
        expression="wavelength/period",
        variables=(
            var("wavelength", r"\lambda", "meter", words=("wavelength",), needs_words=True),
            var("period", "T", "second", words=LABELS["period"], needs_words=True),
        ),
        binding=Binding(
            asks=("wave speed", "speed", "how fast", "velocity"),
            result=("meter / second",),
            inputs=(frozenset({"wavelength", "period"}),),
            nonnegative=True,
        ),
    ),
)
