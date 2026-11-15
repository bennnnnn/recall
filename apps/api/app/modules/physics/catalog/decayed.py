"""What a decaying sample has lost: the share or the mass that decayed, 1 - (1/2)^n of it.

"What percentage has decayed after 2 half-lives?" asks what went, not what is left: read as
the share left, it was 25% for 75% (review 2026-11-13). Each law here is the twin of one of
what is left (``half_life_fraction``, ``percent_after_half_lives``, ``fraction_after_half_lives``,
``half_life_remaining``), cued by an asked share the words call gone (``decay_share``); those
laws give way to them by the same reading.
"""

from __future__ import annotations

from app.modules.physics.catalog.modern import ELAPSED, HALF_LIFE
from app.modules.physics.decay_share import ASKED_GONE_MARKER
from app.services.law_binding.spec import Binding, FormulaSpec, FormulaVariant, formula, var

_LAW = "Radioactive-decay law"
_FRACTION_ASKS = ("fraction", "proportion")
_PERCENT_ASKS = ("percentage", "percent", "what percent")
_N_HALVES = var(
    "n_halves",
    "n",
    dimensionless=True,
    words=("half-lives", "half lives", "half-life", "half life"),
    needs_words=True,
)
_DECAYED = r"1 - \frac{N}{N_0}"


def _share(
    operation: str, asks: tuple[str, ...], result: str, scale: str
) -> tuple[FormulaSpec, ...]:
    """The share decayed after a time and after a number of half-lives, as ``scale`` times
    the fraction (1 or 100)."""
    times = "" if scale == "1" else f"{scale}*"
    return (
        formula(
            f"{operation}_after_time",
            "modern",
            _LAW,
            _DECAYED,
            base_latex=r"\frac{N}{N_0} = \left(\frac{1}{2}\right)^{t/T_{1/2}}",
            expression=f"{times}(1 - (1/2)**(elapsed/half_life))",
            variables=(ELAPSED, HALF_LIFE),
            binding=Binding(
                asks=asks,
                result=(result,),
                inputs=(frozenset({"elapsed", "half_life"}),),
                cues=(ASKED_GONE_MARKER,),
                nonnegative=True,
            ),
        ),
        formula(
            f"{operation}_after_half_lives",
            "modern",
            _LAW,
            _DECAYED,
            base_latex=r"\frac{N}{N_0} = \left(\frac{1}{2}\right)^{n}",
            expression=f"{times}(1 - (1/2)**n_halves)",
            variables=(_N_HALVES,),
            binding=Binding(
                asks=asks,
                result=(result,),
                inputs=(frozenset({"n_halves"}),),
                cues=(ASKED_GONE_MARKER,),
                nonnegative=True,
            ),
        ),
    )


SPECS: tuple[FormulaSpec, ...] = (
    *_share("fraction_decayed", _FRACTION_ASKS, "dimensionless", "1"),
    *_share("percent_decayed", _PERCENT_ASKS, "percent", "100"),
    # The mass that decayed: m₀(1 - (1/2)^(t/T½)). 100 g after two half-lives lost 75 g.
    formula(
        "mass_decayed",
        "modern",
        _LAW,
        r"m_{\text{decayed}}",
        base_latex=r"m_{\text{decayed}} = m_0\left(1 - \left(\frac{1}{2}\right)^{t/T_{1/2}}\right)",
        expression="m*(1 - (1/2)**(elapsed/half_life))",
        variants=(
            FormulaVariant(
                latex=r"m_{\text{decayed}} = m_0\left(1 - \left(\frac{1}{2}\right)^{n}\right)",
                present=frozenset({"n_halves"}),
                expression="m*(1 - (1/2)**n_halves)",
            ),
        ),
        variables=(ELAPSED, HALF_LIFE, var("m", "m_0", "kilogram"), _N_HALVES),
        binding=Binding(
            # "How much of a 100 g sample has decayed": the ask's clause starts after "how much".
            asks=("how much", "mass", "amount", "decayed"),
            result=("kilogram",),
            inputs=(frozenset({"m", "elapsed", "half_life"}), frozenset({"m", "n_halves"})),
            cues=(ASKED_GONE_MARKER,),
            nonnegative=True,
        ),
    ),
)
