"""The STEM sweep's LaTeX check: what a reply may hold so the phone shows no source."""

from __future__ import annotations

import pytest

from app.tests.behavior.latex_check import drawn_commands, latex_problems


@pytest.mark.parametrize(
    ("reply", "problems"),
    [
        ("$v = \\frac{d}{t} = 5\\,\\mathrm{m/s}$", []),
        ("$$\\begin{aligned} a &= b \\\\ &= c \\end{aligned}$$", []),
        ("\\(\\alpha\\) and \\[\\int_0^1 x\\,dx\\]", []),
        ("```answer\n\\frac{1}{2}\n```", []),
        ("```math\n\\sqrt{2}\n```", []),
        ("`\\frac{a}{b}` is how you write it", []),
        ('```graph\n{"label": "\\u2192"}\n```', []),
        ("Then \\frac{1}{2} in prose", ["TeX outside maths: \\frac"]),
        ("The area is 25 m^{2}.", ["TeX outside maths: ^{"]),
        ("$C = \\$0.15\\mathrm{/kWh}$ and $\\$2$", []),
        ("$\\nosuchcommand{x}$", ["the phone draws no \\nosuchcommand"]),
        # A word group's text is drawn as written: a brace after an escaped underscore,
        # or one that opens nothing, is source (2026-11-12); a script or a command is not.
        (
            "$\\text{white\\_{pigment}} = 3 \\times 4$",
            ["a brace in a word group: \\text{white\\_{pigment}}"],
        ),
        ("$\\mathrm{a{b}c} = 1$", ["a brace in a word group: \\mathrm{a{b}c}"]),
        (
            "```answer\n\\text{ratio\\_{total}} = 7\n```",
            ["a brace in a word group: \\text{ratio\\_{total}}"],
        ),
        ("$\\text{white}_{\\text{pigment}} = 12\\,\\mathrm{gallons}$", []),
        ("$\\text{white_{pigment}}$ and $\\mathrm{SO_4^{2-}}$ and $\\mathrm{m/s^{2}}$", []),
        ("$\\text{white\\_pigment}$ and $\\text{\\textdegree}$ and $\\mathrm{\\{x\\}}$", []),
        ("```answer\n\\nosuchcommand{1}\n```", ["the phone draws no \\nosuchcommand"]),
        # A dollar the phone pairs with none is shown (2026-11-13): a ratio read as a price
        # left "5$ ratio" on screen. Prices, tiers, escaped and display dollars are no such.
        ("Check: $9: 12: 15$ is the $3: 4: 5$ ratio.", []),
        ("Check: $9: 12: 15 $ is the $ 3: 4: 5$ ratio.", []),
        ("It is $x$ and 5$ more.", ["a dollar shown as source: It is $x$ and 5$ more."]),
        ("It costs $5 and $10, a ($$) place, \\$3 back, $$x = 2$$ and `$y`.", []),
        ("The price $38.40 = $ 19.20 each.", []),
    ],
)
def test_latex_problems_flags_what_a_reader_would_see_as_source(
    reply: str, problems: list[str]
) -> None:
    assert latex_problems(reply) == problems


def test_drawn_commands_hold_the_phones_list() -> None:
    assert {"frac", "sqrt", "mathrm", "text", "alpha", "sin", "ce", "SI"} <= drawn_commands()
