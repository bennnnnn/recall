"""Right working in every kind of unit the check reads, and a few it must leave alone: the
check changes nothing and names nothing in any of it (review of #2612: a right 26.18 rad/s,
a right 632.8 × 10⁻⁹ m and a right 126.85 °C were each "corrected").

Each reply is built from values worked here, so every line and every card is right: angular
speed from rev/min, wavelengths in nm put in as metres, temperatures in °C and K, km/h and
km h⁻¹, percentages, degrees and radians, cm and m, g and kg, hours and minutes, kJ and MJ,
kPa, atm and mmHg. The working check runs on each whole (``working_pass``)."""

# ruff: noqa: RUF002, RUF003 -- the replies write × and − as models do.

from __future__ import annotations

import math
from collections.abc import Iterator

import pytest

from app.modules.chat.working_pass import checked_working
from app.services.rounding_rule import number_latex

G = 9.81
C = 3.00e8


def _tex(value: float, figures: int = 6) -> str:
    """A working line's number: six figures, a power of ten for a huge or tiny one."""
    if value != 0 and (abs(value) >= 1e6 or abs(value) < 1e-3):
        exponent = math.floor(math.log10(abs(value)))
        mantissa = f"{value / 10**exponent:.{figures - 1}g}"
        return f"{mantissa} \\times 10^{{{exponent}}}"
    return f"{value:.{figures}g}"


def _card(value: float, unit: str) -> str:
    return f"\n\n**Answer**\n\n```answer\nverified: false\n{number_latex(value)}{unit}\n```"


def _reply(*lines: str, card: tuple[float, str]) -> str:
    working = "  \n".join(f"${line}$" for line in lines)
    return f"**Solution**\n\n**Substitution**  \n{working}" + _card(*card)


def _angular() -> Iterator[tuple[str, str]]:
    for n in (250, 300, 1200, 33, 4800, 90, 45, 750):
        w = 2 * math.pi * n / 60
        yield (
            _reply(
                f"N = {n}\\,\\mathrm{{rev/min}} = {_tex(w)}\\,\\mathrm{{rad/s}}",
                f"\\omega = \\frac{{2\\pi \\times {n}}}{{60}}",
                f"\\omega = {_tex(w)}\\,\\mathrm{{rad/s}}",
                card=(w, "\\,\\mathrm{rad/s}"),
            ),
            f"A wheel turns at {n} rev/min.",
        )
        r = 0.30
        yield (
            _reply(
                f"\\omega = {n}\\,\\mathrm{{rev/min}} = {_tex(w)}\\,\\mathrm{{rad/s}}",
                f"v = {_tex(w)} \\times {r}",
                f"v = {_tex(w * r)}\\,\\mathrm{{m/s}}",
                card=(w * r, "\\,\\mathrm{m/s}"),
            ),
            f"A wheel of radius 0.30 m turns at {n} rev/min.",
        )


def _wavelengths() -> Iterator[tuple[str, str]]:
    for nm in (632.8, 550.0, 405.0, 700.0, 589.3, 486.1, 656.3, 532.0):
        f = C / (nm * 1e-9)
        yield (
            _reply(
                f"\\lambda = {nm}\\,\\mathrm{{nm}} = {nm} \\times 10^{{-9}}\\,\\mathrm{{m}}",
                "f = \\frac{c}{\\lambda}",
                f"f = \\frac{{3.00 \\times 10^{{8}}}}{{{nm} \\times 10^{{-9}}}}",
                f"f = {_tex(f)}\\,\\mathrm{{Hz}}",
                card=(f, "\\,\\mathrm{Hz}"),
            ),
            f"Light of wavelength {nm} nm.",
        )
        energy = 6.63e-34 * f
        yield (
            _reply(
                f"f = {_tex(f)}\\,\\mathrm{{Hz}}",
                f"E = 6.63 \\times 10^{{-34}} \\times {_tex(f)}",
                f"E = {_tex(energy)}\\,\\mathrm{{J}}",
                card=(energy, "\\,\\mathrm{J}"),
            ),
            f"Light of wavelength {nm} nm.",
        )


def _temperatures() -> Iterator[tuple[str, str]]:
    for celsius in (25.0, 100.0, 37.0, -40.0, 0.0, 126.85, 15.5, 60.0):
        kelvin = celsius + 273.15
        yield (
            _reply(
                f"T = {celsius}\\,^\\circ\\mathrm{{C}} = {_tex(kelvin)}\\,\\mathrm{{K}}",
                f"T_2 = 2 \\times {_tex(kelvin)}",
                f"T_2 = {_tex(2 * kelvin)}\\,\\mathrm{{K}} = {_tex(2 * kelvin - 273.15)}\\,^\\circ\\mathrm{{C}}",
                card=(2 * kelvin - 273.15, "\\,^\\circ\\mathrm{C}"),
            ),
            f"A gas at {celsius} °C has its kelvin temperature doubled.",
        )
        fahrenheit = celsius * 9 / 5 + 32
        yield (
            _reply(
                f"T_F = \\frac{{9}}{{5}} \\times {celsius} + 32",
                f"T_F = {_tex(fahrenheit)}\\,^\\circ\\mathrm{{F}}",
                card=(fahrenheit, "\\,^\\circ\\mathrm{F}"),
            ),
            f"Convert {celsius} °C to °F.",
        )


def _speeds() -> Iterator[tuple[str, str]]:
    for kmh in (72, 90, 36, 120, 54, 18, 108, 45):
        ms = kmh / 3.6
        t = 15
        yield (
            _reply(
                f"v = {kmh}\\,\\mathrm{{km}}\\,\\mathrm{{h}}^{{-1}} = {_tex(ms)}\\,\\mathrm{{m}}\\,\\mathrm{{s}}^{{-1}}",
                f"d = {_tex(ms)} \\times {t}",
                f"d = {_tex(ms * t)}\\,\\mathrm{{m}}",
                card=(ms * t, "\\,\\mathrm{m}"),
            ),
            f"A car at {kmh} km/h for {t} s.",
        )
        yield (
            _reply(
                f"v = {kmh}\\,\\mathrm{{km/h}} = \\frac{{{kmh}}}{{3.6}} = {_tex(ms)}\\,\\mathrm{{m/s}}",
                f"t = \\frac{{100}}{{{_tex(ms)}}}",
                f"t = {_tex(100 / ms)}\\,\\mathrm{{s}}",
                card=(100 / ms, "\\,\\mathrm{s}"),
            ),
            f"How long does a car at {kmh} km/h take for 100 m?",
        )


def _percentages() -> Iterator[tuple[str, str]]:
    for useful, total in ((300, 400), (45, 60), (1200, 1500), (8.5, 10), (72, 90), (3.3, 4.4)):
        share = useful / total * 100
        yield (
            _reply(
                f"\\eta = \\frac{{{useful}}}{{{total}}} \\times 100",
                f"\\eta = {_tex(share)}\\,\\%",
                card=(share, "\\,\\%"),
            ),
            f"{useful} J useful out of {total} J.",
        )


def _angles() -> Iterator[tuple[str, str]]:
    for degrees in (30, 45, 60, 37, 53, 20, 75, 10):
        radians = math.radians(degrees)
        force = 50 * math.cos(radians)
        yield (
            _reply(
                f"\\theta = {degrees}^\\circ = {_tex(radians)}\\,\\mathrm{{rad}}",
                f"F_x = 50 \\times \\cos({degrees}^\\circ)",
                f"F_x = {_tex(force)}\\,\\mathrm{{N}}",
                card=(force, "\\,\\mathrm{N}"),
            ),
            f"A 50 N force at {degrees}° to the horizontal.",
        )
        yield (
            _reply(
                f"\\theta = {_tex(radians)}\\,\\mathrm{{rad}} = {degrees}^\\circ",
                f"s = 2.0 \\times {_tex(radians)}",
                f"s = {_tex(2 * radians)}\\,\\mathrm{{m}}",
                card=(degrees, "^\\circ"),
            ),
            f"An arc of radius 2.0 m turns {degrees}°.",
        )


def _lengths_and_masses() -> Iterator[tuple[str, str]]:
    for cm in (9.00, 2.50, 12.0, 0.30, 45.0, 7.5):
        m = cm / 100
        yield (
            _reply(
                f"r = {cm}\\,\\mathrm{{cm}} = {_tex(m)}\\,\\mathrm{{m}}",
                f"A = \\pi \\times ({_tex(m)})^2",
                f"A = {_tex(math.pi * m**2)}\\,\\mathrm{{m^2}}",
                card=(math.pi * m**2, "\\,\\mathrm{m^2}"),
            ),
            f"A circle of radius {cm} cm.",
        )
        yield (
            _reply(
                f"r = {cm}\\,\\mathrm{{cm}}",
                "A = \\pi r^2",
                f"A = \\pi ({cm})^2",
                f"A = {_tex(math.pi * cm**2)}\\,\\mathrm{{cm^2}}",
                card=(math.pi * cm**2, "\\,\\mathrm{cm^2}"),
            ),
            f"A circle of radius {cm} cm.",
        )
    for grams in (500, 250, 75, 1200, 20, 640):
        kg = grams / 1000
        yield (
            _reply(
                f"m = {grams}\\,\\mathrm{{g}} = {_tex(kg)}\\,\\mathrm{{kg}}",
                f"W = {_tex(kg)} \\times 9.81",
                f"W = {_tex(kg * G)}\\,\\mathrm{{N}}",
                card=(kg * G, "\\,\\mathrm{N}"),
            ),
            f"The weight of {grams} g.",
        )
        v = 3
        yield (
            _reply(
                f"m = {grams}\\,\\mathrm{{g}} = {_tex(kg)}\\,\\mathrm{{kg}}",
                f"v = {v}\\,\\mathrm{{m/s}}",
                f"K = \\frac{{1}}{{2}} \\times {_tex(kg)} \\times {v}^2",
                f"K = {_tex(0.5 * kg * v**2)}\\,\\mathrm{{J}}",
                card=(0.5 * kg * v**2, "\\,\\mathrm{J}"),
            ),
            f"A {grams} g ball at 3 m/s.",
        )


def _times_and_energies() -> Iterator[tuple[str, str]]:
    for hours, power in ((2, 1500), (0.5, 60), (1.5, 2000), (3, 100), (0.25, 800), (4, 250)):
        seconds = hours * 3600
        energy = power * seconds
        yield (
            _reply(
                f"t = {hours}\\,\\mathrm{{h}} = {_tex(hours * 60)}\\,\\mathrm{{min}} = {_tex(seconds)}\\,\\mathrm{{s}}",
                f"E = {power} \\times {_tex(seconds)}",
                f"E = {_tex(energy)}\\,\\mathrm{{J}} = {_tex(energy / 1000)}\\,\\mathrm{{kJ}}",
                card=(energy / 1000, "\\,\\mathrm{kJ}"),
            ),
            f"A {power} W heater runs for {hours} h.",
        )
        yield (
            _reply(
                f"E = {_tex(energy)}\\,\\mathrm{{J}} = {_tex(energy / 1e6)}\\,\\mathrm{{MJ}}",
                card=(energy / 1e6, "\\,\\mathrm{MJ}"),
            ),
            f"A {power} W heater runs for {hours} h.",
        )


def _pressures() -> Iterator[tuple[str, str]]:
    for kpa in (101.325, 250.0, 75.0, 120.0, 33.0, 202.65):
        pa = kpa * 1000
        atm = kpa / 101.325
        mmhg = atm * 760
        yield (
            _reply(
                f"p = {kpa}\\,\\mathrm{{kPa}} = {_tex(pa)}\\,\\mathrm{{Pa}}",
                f"F = {_tex(pa)} \\times 0.020",
                f"F = {_tex(pa * 0.020)}\\,\\mathrm{{N}}",
                card=(pa * 0.020, "\\,\\mathrm{N}"),
            ),
            f"A pressure of {kpa} kPa on 0.020 m².",
        )
        yield (
            _reply(
                f"p = \\frac{{{kpa}}}{{101.325}}",
                f"p = {_tex(atm)}\\,\\mathrm{{atm}} = {_tex(mmhg)}\\,\\mathrm{{mmHg}}",
                card=(mmhg, "\\,\\mathrm{mmHg}"),
            ),
            f"Write {kpa} kPa in mmHg.",
        )


_CORPUS = [
    *_angular(),
    *_wavelengths(),
    *_temperatures(),
    *_speeds(),
    *_percentages(),
    *_angles(),
    *_lengths_and_masses(),
    *_times_and_energies(),
    *_pressures(),
]


def test_the_corpus_is_large() -> None:
    lines = sum(reply.count("$") // 2 for reply, _question in _CORPUS)
    assert len(_CORPUS) >= 100
    assert lines >= 150


@pytest.mark.parametrize(("reply", "question"), _CORPUS)
def test_right_working_in_any_unit_is_left_as_it_is(reply: str, question: str) -> None:
    text = checked_working(reply, question, school=True, laid_out=False, decimal_comma=False)
    assert text == reply
