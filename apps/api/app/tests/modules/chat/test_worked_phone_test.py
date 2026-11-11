# ruff: noqa: RUF002 -- the blocks hold the Greek letters and dashes models write.
r"""The ```worked blocks of the owner's 2026-11-11 phone test, laid out as the phone shows them.

DeepSeek wrote LaTeX into a block's words ("Substitution x = \tan t", "evenness of
\ln\cos t", "value of the solution at x = \pi/3") and the layout put it on screen as
source; a pure number's unit came out as a dash (``f = ½ —``); letters the question gave as
quantities read "C = C F" or were dropped; a formula with no name was headed by a bare
**Formula**; and the unknown was ``ρ`` under Required but ``\rho`` in the working. Each
block below is the kind the model wrote, look-alikes beside it.
"""

from __future__ import annotations

import itertools

import pytest

from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.worked_render import WorkedLayout
from app.modules.chat.worked_stream import ReplyFilter, WorkedFilter
from app.modules.chat.worked_text import greek_as_commands, prose_maths
from app.modules.chat.worked_units import unit_tex
from app.tests.behavior.latex_check import latex_problems

PHYSICS = WorkedLayout(law_heading=True)
OTHER = WorkedLayout()

INTEGRAL = r"""```worked
given: I | \int_0^1 \frac{\ln(1+x)}{1+x^2}\,dx | | definite integral
required: I | value of the definite integral
formula: Substitution x = \tan t | I = \int_0^{\pi/4} \ln(1+\tan t)\,dt
step: 1+\tan t = \frac{\sqrt{2}\cos\left(t-\frac{\pi}{4}\right)}{\cos t} | trigonometric identity
step: \int_0^{\pi/4} \ln\cos\left(t-\frac{\pi}{4}\right)\,dt = \int_0^{\pi/4}\ln\cos t\,dt | evenness of \ln\cos t
substitution: I = \frac{\pi}{8}\ln 2
answer: I | \frac{\pi}{8}\ln 2 | | B
```"""
ODE = r"""```worked
given: y(0) | 1 | | initial condition
given: x | \pi/3 | rad | point where y is evaluated
required: y(\pi/3) | value of the solution at x = \pi/3
formula: Integrating factor method | \frac{dy}{dx} + y\tan x = \cos^{3}x
step: \mu = e^{\int \tan x\,dx} | Integrating factor
step: y\sec x = \int \sec x\cos^{3}x\,dx | multiply through by \mu = \sec x
solve_for: y | y = \cos x\left(\frac{x}{2} + \frac{\sin 2x}{4} + C\right)
substitution: y = 0.870
answer: y(\pi/3) | 0.870 | | to 3 s.f.
```"""
SHEEP = r"""```worked
given: P_b | 4 | birr | buying price of the sheep
given: f | \frac{1}{2} | — | profit as a fraction of the buying price
required: P_s | selling price
formula: Profit | \text{profit} = f \times P_b
substitution: P_s = 4 + 2
substitution: P_s = 6\,\text{birr}
answer: P_s | 6 | birr
```"""
CYLINDER = r"""```worked
given: g\sin\theta | 6.0 | m/s^2 | component of gravitational acceleration down the slope
given: I | \frac{1}{2}MR^2 | — | moment of inertia of a uniform solid cylinder
required: a | linear acceleration of the center of mass
formula: Rolling without slipping | a = \frac{g\sin\theta}{1 + \frac{I}{MR^2}}
substitution: a = \frac{6.0}{1.5}
substitution: a = 4.0\,\mathrm{m/s^2}
answer: a | 4.0 | m/s^2 | down the incline
```"""
RLC = r"""```worked
given: C | C | F | capacitance
given: V_0 | V_0 | V | initial potential difference
given: R | R | Ω | resistance
given: Q_0 | C V_0 | C | initial charge on the capacitor
required: t | time when the charge first reaches zero
formula: Damped charge oscillation | q(t)=Q_0 e^{-\frac{R}{2L}t}\cos(\omega_d t)
substitution: t=\frac{1}{\omega_d}\left[\frac{\pi}{2}+\arctan\left(\frac{R}{2L\omega_d}\right)\right]
answer: t | \frac{1}{\omega_d}\left[\frac{\pi}{2}+\arctan\left(\frac{R}{2L\omega_d}\right)\right] | s
```"""
ROD = r"""```worked
given: M | | | mass of the rod
given: L | length of the rod
given: m | m | kg | small mass at the free end
required: α | angular acceleration immediately after release
formula: Newton's second law for rotation | \tau = I\alpha
solve_for: α | \alpha = \frac{\tau}{I}
substitution: \alpha = \frac{g\left(\frac{M}{2} + m\right)}{L\left(\frac{M}{3} + m\right)}
answer: α | \frac{g\left(\frac{M}{2}+m\right)}{L\left(\frac{M}{3}+m\right)} | rad/s^2
```"""
DENSITY = r"""```worked
given: m | 100 | g | mass
given: V | 20 | cm³ | volume
required: ρ | density
formula: Density formula | ρ = \frac{m}{V}
substitution: ρ = \frac{100}{20}
substitution: ρ = 5\,\mathrm{g/cm^3}
answer: ρ | 5 | g/cm³
```"""
SPRING = r"""```worked
given: m | 2.0 | kg | mass of the block
given: k | 400 | N/m | spring constant
required: x | maximum compression of the spring
formula: m g h = \frac{1}{2} k x^{2}
solve_for: x | x = \sqrt{\frac{2 m g h}{k}}
substitution: x = 0.71\,\mathrm{m}
answer: x | 0.71 | m
```"""
BLOCKS = {
    "integral": INTEGRAL,
    "ode": ODE,
    "sheep": SHEEP,
    "cylinder": CYLINDER,
    "rlc": RLC,
    "rod": ROD,
    "density": DENSITY,
    "spring": SPRING,
}


def _laid_out(block: str, layout: WorkedLayout = PHYSICS) -> str:
    worked = WorkedFilter(layout)
    worked.feed(block)
    worked.close()
    return worked.text


@pytest.mark.parametrize(("name", "block"), BLOCKS.items())
@pytest.mark.parametrize("layout", [PHYSICS, OTHER])
def test_no_heading_note_or_meaning_shows_latex_source(
    name: str, block: str, layout: WorkedLayout
) -> None:
    """latex_check holds every piece the layout writes from the model's words: a heading,
    a move's note, what a given or the unknown is."""
    assert latex_problems(_laid_out(block, layout)) == [], name


@pytest.mark.parametrize(
    ("block", "shown"),
    [
        (INTEGRAL, "**Substitution $x = \\tan t$**  \n$I = \\int_0^{\\pi/4}"),
        (INTEGRAL, "— evenness of $\\ln\\cos t$"),
        (ODE, "$y(\\pi/3)$ (value of the solution at $x = \\pi/3$)"),
        (ODE, "— multiply through by $\\mu = \\sec x$"),
        (ODE, "**Integrating factor method**  \n"),
    ],
)
def test_maths_in_the_models_words_is_drawn_as_maths(block: str, shown: str) -> None:
    assert shown in _laid_out(block)


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        (r"evenness of \ln\cos t", r"evenness of $\ln\cos t$"),
        (r"multiply through by \mu = \sec x", r"multiply through by $\mu = \sec x$"),
        (r"(value at x = \pi/3)", r"(value at $x = \pi/3$)"),
        (r"the \Delta x is small", r"the $\Delta x$ is small"),
        (r"speed v_0 at the start", r"speed $v_0$ at the start"),
        (r"f(x) = \sin x on the interval", r"$f(x) = \sin x$ on the interval"),
        # Look-alikes: a word beside the maths stays a word, and words stay words.
        (r"is a \sqrt{2} away", r"is a $\sqrt{2}$ away"),
        (r"\sqrt{2} a lot", r"$\sqrt{2}$ a lot"),
        ("profit_per_sheep in total", "profit per sheep in total"),
        ("apply y(0) = 1", "apply y(0) = 1"),
        ("the exponential factor is never zero", "the exponential factor is never zero"),
    ],
)
def test_prose_maths_marks_each_run_of_maths(text: str, shown: str) -> None:
    assert prose_maths(text) == shown


@pytest.mark.parametrize(
    "unit", ["—", "-", "–", "none", "None", "dimensionless", "unitless", "n/a"]
)
def test_a_pure_number_shows_no_unit(unit: str) -> None:
    assert unit_tex(unit) == ""


@pytest.mark.parametrize(
    ("unit", "tex"),
    [("nA", r"\,\mathrm{nA}"), ("N/A", r"\,\mathrm{N/A}"), ("%", r"\,\%"), ("°", r"^\circ")],
)
def test_a_unit_that_looks_like_a_placeholder_stays(unit: str, tex: str) -> None:
    assert unit_tex(unit) == tex


@pytest.mark.parametrize(
    ("block", "shown", "not_shown"),
    [
        (SHEEP, "$f = \\frac{1}{2}$  \n", "—"),
        (CYLINDER, "$I = \\frac{1}{2}MR^2$  \n", "—"),
    ],
)
def test_a_unitless_given_has_no_dash_for_a_unit(block: str, shown: str, not_shown: str) -> None:
    laid_out = _laid_out(block)
    assert shown in laid_out
    assert not_shown not in laid_out


def test_a_given_stated_as_a_letter_is_listed_by_its_meaning() -> None:
    laid_out = _laid_out(RLC)
    given = laid_out.split("**Required**")[0]
    assert "$C$ (capacitance)  \n$V_0$ (initial potential difference)  \n$R$ (resistance)" in given
    # Never "C = C F", and the letters are named on their own line, not again under where.
    assert "C = C" not in given and "V_0 = V_0" not in given
    assert "where $Q_0$ = initial charge on the capacitor" in given
    assert "$C$ =" not in given
    # A value written in symbols carries its units in them: no unit after it.
    assert "$Q_0 = C V_0$" in given
    assert laid_out.rstrip().endswith("\\right)\\right]$")


def test_letters_with_no_value_are_never_dropped() -> None:
    given = _laid_out(ROD).split("**Required**")[0]
    assert given.startswith(
        "**Given**  \n$M$ (mass of the rod)  \n$L$ (length of the rod)  \n"
        "$m$ (small mass at the free end)"
    )


@pytest.mark.parametrize("block", [DENSITY, ROD])
def test_a_greek_unknown_is_one_symbol_in_every_line(block: str) -> None:
    laid_out = _laid_out(block)
    assert "ρ" not in laid_out and "α" not in laid_out
    assert "$\\rho$ (density)" in laid_out or "$\\alpha$ (angular acceleration" in laid_out


@pytest.mark.parametrize(
    ("tex", "commands"),
    [
        ("ρ = \\frac{m}{V}", "\\rho = \\frac{m}{V}"),
        ("ρV", "\\rho V"),
        ("Δx + θ", "\\Delta x + \\theta"),
        # A unit's letters are text: μC stays as written.
        ("q = 2\\,\\mathrm{μC}", "q = 2\\,\\mathrm{μC}"),
        ("Ω", "\\Omega"),
    ],
)
def test_greek_letters_in_maths_are_their_commands(tex: str, commands: str) -> None:
    assert greek_as_commands(tex) == commands


def test_a_formula_with_no_name_is_never_headed_formula() -> None:
    laid_out = _laid_out(SPRING)
    assert "**Formula**" not in laid_out
    assert "**Solution**\n\n$m g h = \\frac{1}{2} k x^{2}$  \nSolve for $x$" in laid_out


@pytest.mark.parametrize("block", BLOCKS.values())
def test_the_phone_test_blocks_stream_without_a_rewrite(block: str) -> None:
    accum = StreamAccum()
    reply_filter = ReplyFilter(accum, PHYSICS)
    seen: list[str] = []
    for start in range(0, len(block), 7):
        if sent := reply_filter.feed(block[start : start + 7]):
            accum.shown.append(sent)
        seen.append("".join(accum.shown))
    if tail := reply_filter.flush():
        accum.shown.append(tail)
    assert not accum.rewritten
    for earlier, later in itertools.pairwise(seen):
        assert later.startswith(earlier)
    assert "".join(accum.shown).strip() == _laid_out(block).strip()
