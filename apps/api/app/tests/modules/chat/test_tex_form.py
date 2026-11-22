"""TeX a model wrote, in the form the phone draws: open groups closed, one script of each kind
on a base (the owner's chat, 2026-11-20: ``v_A_{vec}`` and ``\\mathrm{m/s`` shown as source)."""

from __future__ import annotations

import pytest

from app.modules.chat.tex_form import well_formed


@pytest.mark.parametrize(
    ("tex", "shown"),
    [
        # A second subscript is more of the first: one subscript naming both (2026-11-21).
        ("v_A_{vec}, v_B_{vec}", "v_{A,vec}, v_{B,vec}"),
        ("r_{frustum}_{top}", "r_{frustum,top}"),
        ("V_{small}_{cone}_{volume}", "V_{small,cone,volume}"),
        ("x^2^3", "{x^2}^3"),
        ("x_a^b_c", "{x_a^b}_c"),
        # Inside a group as well (Claude on #2509).
        (r"\frac{v_A_{vec}}{2}", r"\frac{v_{A,vec}}{2}"),
        (r"\sqrt{x_1_2}", r"\sqrt{x_{1,2}}"),
        ("e^{x^2^3}", "e^{{x^2}^3}"),
        (r"(-16\hat{i} + 0\hat{j})\ \mathrm{m/s", r"(-16\hat{i} + 0\hat{j})\ \mathrm{m/s}"),
        (r"\frac{1}{2", r"\frac{1}{2}"),
        # Already drawn as written.
        ("x_1^2", "x_1^2"),
        ("v_{2x}^2", "v_{2x}^2"),
        (r"\vec{v}_A", r"\vec{v}_A"),
        (r"e^{i\pi}", r"e^{i\pi}"),
        (r"\{x \mid x > 0\}", r"\{x \mid x > 0\}"),
        (r"\left(\frac{a}{b}\right)^2", r"\left(\frac{a}{b}\right)^2"),
        (r"v_{\max}^2", r"v_{\max}^2"),
        ("H_2O", "H_2O"),
        (r"a \\ b", r"a \\ b"),
    ],
)
def test_well_formed(tex: str, shown: str) -> None:
    assert well_formed(tex) == shown


@pytest.mark.parametrize(
    ("tex", "shown"),
    [("a}", "a"), (r"\frac{1}{2}}", r"\frac{1}{2}"), ("}x{", "x{}")],
)
def test_a_brace_that_closes_nothing_is_left_out(tex: str, shown: str) -> None:
    assert well_formed(tex) == shown
