"""The verified card in the form the reply's working reaches (``math.card_form``).

The unit-5 round (2026-11-16) showed checked cards in SymPy's own form under working that
reaches another: csc(2x + π/4)/2 under ½ sec(2x - π/4), ln|2 cos 2t - 2|/2 under
ln|1 - cos 2t|/2 (a constant apart), one fraction under the partial fractions it came from.
The card shows the working's value when SymPy finds it the same, and the server's otherwise.
Only for an antiderivative: a factorisation, an expansion, a simplification or a definite
value keeps the server's form, whatever equal value the working ends on (review, 2026-11-16).
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.card_form import in_working_form, read_tex
from app.modules.math.fence import validate_math_fences
from app.modules.math.tools import _build_verified_block, extract_math_intent
from app.services.solving import VerifiedMathBlock

_SEC = r"\frac{\csc{\left(2 x + \frac{\pi}{4} \right)}}{2} + C"
_LOG = r"\frac{\ln\left|2 \cos{\left(2 t \right)} - 2\right|}{2} + C"
_FRACTIONS = (
    r"\frac{\left(x + 1\right) \left(x + 4 \ln\left|x + 1\right| - 8 \ln\left|x + 2\right|\right)"
    r" + 1}{x + 1} + C"
)


def _reply(*lines: str) -> str:
    return "\n".join(["**Solution**", *lines, "", "**Answer**", ""])


@pytest.mark.parametrize(
    ("reply", "server", "card"),
    [
        # An equivalent form: the working's.
        (
            _reply(r"$\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right) + C$"),
            _SEC,
            r"\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right) + C",
        ),
        # An antiderivative a constant apart (ln 2 / 2): still the working's.
        (
            _reply(r"$\frac{\ln|1 - \cos(2t)|}{2} + C$"),
            _LOG,
            r"\frac{\ln|1 - \cos(2t)|}{2} + C",
        ),
        # The line names what it integrates: the card holds the value.
        (
            _reply(r"$= x + 4\ln|x+1| + \frac{1}{x+1} - 8\ln|x+2| + C$"),
            _FRACTIONS,
            r"x + 4\ln|x+1| + \frac{1}{x+1} - 8\ln|x+2| + C",
        ),
        # The working's last line before its constant: the card writes the + C.
        (
            _reply(r"$\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right)$"),
            _SEC,
            r"\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right) + C",
        ),
        # The working stops in u: the Answer's own line is the reply's form.
        (
            "**Solution**\n$u = 2x$\n\n**Answer**\n"
            r"$\int \sec u \tan u\,dx = \frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right) + C$",
            _SEC,
            r"\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right) + C",
        ),
        # A braced power in a fraction (e^{2x} is e^(2x), never e^2 x).
        (
            _reply(r"$\frac{2e^{2x} - 18e^x - 12}{3\sqrt{e^x}} + C$"),
            r"\frac{2 \left(\left(e^{x} - 9\right) e^{x} - 6\right)}{3 \sqrt{e^{x}}} + C",
            r"\frac{2e^{2x} - 18e^x - 12}{3\sqrt{e^x}} + C",
        ),
        # The Answer copies the server's form: the working's last line is the reply's own.
        (
            "**Solution**\n$= \\frac{\\ln|1 - \\cos(2t)|}{2} + C$\n\n**Answer**\n$" + _LOG + "$",
            _LOG,
            r"\frac{\ln|1 - \cos(2t)|}{2} + C",
        ),
    ],
)
def test_the_card_shows_the_form_the_working_reaches(reply: str, server: str, card: str) -> None:
    assert in_working_form(reply, server, antiderivative=True) == card


@pytest.mark.parametrize(
    ("reply", "server"),
    [
        # Wrong working keeps the server's value.
        (_reply(r"$\frac{1}{2}\sec\left(2x + \frac{\pi}{4}\right) + C$"), _SEC),
        # Working that never integrates (it stops at a partial-fraction constant).
        (_reply(r"$A = -\dfrac{11}{4}$"), _FRACTIONS),
        # A definite value keeps the server's form: "ln 5 - ln 3" is ln(5/3) unworked.
        (_reply(r"$= \ln 5 - \ln 3$"), r"\ln{\left(\frac{5}{3} \right)}"),
        # A function SymPy would still evaluate is unfinished work, never the card.
        (_reply(r"$x \arctan 1 + C$"), r"\frac{\pi x}{4} + C"),
        (_reply(r"$\sqrt{8}\,x + C$"), r"2 \sqrt{2} x + C"),
        (_reply(r"$e^{\ln x} + C$"), r"x + C"),
        (_reply(r"$x + \ln 1 + C$"), r"x + C"),
        # A term that vanishes at whole numbers is no constant (Codex on #2481).
        (_reply(r"$\frac{x^2}{2} + \sin(\pi x) + C$"), r"\frac{x^{2}}{2} + C"),
        (_reply(r"$\frac{x^2}{2} + x(x - 1)(x + 1) + C$"), r"\frac{x^{2}}{2} + C"),
        # A constant beside the + C is the constant's to carry.
        (_reply(r"$\frac{x^3}{3} + 5 + C$"), r"\frac{x^{3}}{3} + C"),
        # The Answer is read first: a wrong Answer keeps the server's form though the working
        # above it is right.
        (
            "**Solution**\n$\\frac{1}{2}\\sec\\left(2x - \\frac{\\pi}{4}\\right) + C$\n\n"
            "**Answer**\n$\\sec(2x) + C$",
            _SEC,
        ),
        # A definite value never gains a constant.
        (_reply(r"$\ln 5 - \ln 3 + C$"), r"\ln{\left(\frac{5}{3} \right)}"),
        # A fraction in lowest terms is its one form: "27/3 - 0" is 9 unworked.
        (_reply(r"$A = \frac{27}{3} - 0$"), "9"),
        # A number's working is never its card: "0.15 * 85" is 12.75.
        (_reply(r"$0.15 \times 85$"), "12.75"),
        # A rounded decimal never replaces an exact value.
        (_reply(r"$= 0.5108256237659907$"), r"\ln{\left(\frac{5}{3} \right)}"),
        # A sentence states no value.
        (_reply(r"At $x = 1$: $\frac{1}{3}\ln 2$"), r"\frac{\ln 2}{3}"),
        # A card of several values is the server's.
        (_reply("$x = 1$, $y = 3$"), "x = 1, y = 3"),
    ],
)
def test_the_card_keeps_the_servers_form_otherwise(reply: str, server: str) -> None:
    assert in_working_form(reply, server, antiderivative=True) == server


def test_sympys_own_spelling_reads() -> None:
    assert read_tex(r"\cos^{3}{\left(\frac{x}{3} \right)}") is not None
    assert read_tex(_LOG.removesuffix(" + C")) is not None


@pytest.mark.parametrize(
    "line",
    [
        r"\(\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right) + C\)",
        r"\[\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right) + C\]",
        r"\(\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right)\)",
    ],
)
def test_a_line_in_any_maths_delimiter_states_its_form(line: str) -> None:
    """Gemini on #2481: a \\(…\\) line got " + C" outside its delimiter, and a literal \\(
    reached the verified card."""
    card = in_working_form(_reply(line), _SEC, antiderivative=True)
    assert card == r"\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right) + C"


@pytest.mark.parametrize(
    "line",
    [
        r"$\int (4x^3 + 2x)\,dx = 4\cdot\frac{x^4}{4} + 2\cdot\frac{x^2}{2} + C$",
        r"$\int 4x^3\,dx = \frac{4x^{3+1}}{3+1} + C$",
        r"$\int x\,dx = \frac{2}{4}x^2 + C$",
    ],
)
def test_a_working_step_with_numbers_to_combine_is_no_card(line: str) -> None:
    """Gemini on #2481: the last working line can be a step not yet simplified."""
    server = r"x^{4} + x^{2} + C"
    assert in_working_form(_reply(line), server, antiderivative=True) == server


@pytest.mark.parametrize(
    "line", [r"$\frac{3x^2}{2} + C$", r"$-\frac{1}{2}\cos(2x) + C$", r"$\frac{x^3}{3} + C$"]
)
def test_a_finished_fraction_is_no_step(line: str) -> None:
    from app.modules.math.card_form import _uncombined

    assert not _uncombined(read_tex(line.strip("$").removesuffix(" + C"), evaluate=False))


@pytest.mark.parametrize("constant", ["+ C", "- C", "+ c", "-c", ""])
def test_the_constant_is_written_once_as_plus_c(constant: str) -> None:
    """Gemini on #2481: "- C" and "+ c" were no constant, and the card read "- C + C"."""
    reply = _reply(rf"$\frac{{1}}{{2}}\sec\left(2x - \frac{{\pi}}{{4}}\right) {constant}$")
    card = in_working_form(reply, _SEC, antiderivative=True)
    assert card == r"\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right) + C"


def test_a_letter_c_inside_the_form_is_no_constant() -> None:
    reply = _reply(r"$\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right) + c x + C$")
    assert in_working_form(reply, _SEC, antiderivative=True) == _SEC


def test_a_bare_log_is_base_ten() -> None:
    """Review of #2481: Recall reads a bare \\log as base 10 (docs/math.md), so a natural-log
    antiderivative written \\log is no match, and the card keeps the server's \\ln; the
    form written \\ln takes the card."""
    assert read_tex(r"\log(x)") == read_tex(r"\log_{10}(x)")
    assert read_tex(r"\log|x|") != read_tex(r"\ln|x|")
    server = r"\ln\left|x\right| + C"
    assert in_working_form(_reply(r"$\log|x| + C$"), server, antiderivative=True) == server
    assert in_working_form(_reply(r"$\log|2x| + C$"), server, antiderivative=True) == server
    assert in_working_form(_reply(r"$\ln|2x| + C$"), server, antiderivative=True) == (
        r"\ln|2x| + C"
    )


def test_the_fence_pass_lands_the_working_form_checked() -> None:
    verified = VerifiedMathBlock(
        text="", subject="math", canonical_answer=_SEC, antiderivative=True
    )
    reply = _reply(r"$\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right) + C$")
    out = validate_math_fences(reply, verified=verified)
    assert (
        "```answer\nverified: true\n\\frac{1}{2}\\sec\\left(2x - \\frac{\\pi}{4}\\right) + C\n```"
        in out
    )
    assert "csc" not in out


def _block(question: str) -> VerifiedMathBlock:
    intent = extract_math_intent(question)
    assert intent is not None
    block = _build_verified_block(intent, Settings(math_tools_enabled=True))
    assert block is not None and block.canonical_answer
    return block


@pytest.mark.parametrize(
    ("question", "working", "answer"),
    [
        # The review's repros (2026-11-16), through the real block: each working ends on a
        # value equal to the verified one but not its answer.
        ("Factor x^2 - 5x + 6", "$(x-2)(x-3) = x^2 - 5x + 6$", "$(x-2)(x-3)$"),
        ("Expand (x+2)(x-3)", "$(x+2)(x-3) = x^2 - 3x + 2x - 6$", "$(x+2)(x-3)$"),
        ("Simplify (x^2-1)/(x-1)", r"$\frac{x^2-1}{x-1} = \frac{(x-1)(x+1)}{x-1}$", "$x + 1$"),
        ("Evaluate the integral of 1/x from 1 to 2", r"$= \ln 2 - \ln 1$", r"$\ln 2$"),
        (
            "Evaluate the integral of cos x from 0 to pi/4",
            r"$= \sin\frac{\pi}{4} - \sin 0$",
            r"$\frac{\sqrt{2}}{2}$",
        ),
    ],
)
def test_a_card_whose_form_is_its_answer_keeps_the_servers(
    question: str, working: str, answer: str
) -> None:
    block = _block(question)
    reply = f"**Solution**\n{working}\n\n**Answer**\n\n{answer}"
    out = validate_math_fences(reply, verified=block)
    assert f"```answer\nverified: true\n{block.canonical_answer}\n```" in out


_ATAN = r"\operatorname{atan}{\left(x \right)} + C"


@pytest.mark.parametrize(
    ("reply", "server"),
    [
        # Gemini on #2481: a zero derivative is not enough. A jump at a pole …
        (_reply(r"$-\arctan\left(\frac{1}{x}\right) + C$"), _ATAN),
        (_reply(r"$\arctan\left(\frac{x+1}{1-x}\right) + C$"), _ATAN),
        # … a form real on one side of a log's zero only, sampled on both sides …
        (_reply(r"$\ln(6 - x) + C$"), r"\ln\left|x - 6\right| + C"),
        # … wherever the zero lies, outside any window (Gemini on #2481) …
        (_reply(r"$\ln(x - 25) + C$"), r"\ln\left|x - 25\right| + C"),
        (
            _reply(r"$-\arctan\left(\frac{1}{x - 30}\right) + C$"),
            r"\operatorname{atan}{\left(x - 30 \right)} + C",
        ),
        # … and one real nowhere.
        (_reply(r"$\frac{1}{2}\ln(-x^2 - 1) + C$"), r"\frac{\ln\left|x^{2} + 1\right|}{2} + C"),
    ],
)
def test_a_form_with_a_jump_or_another_domain_keeps_the_servers(reply: str, server: str) -> None:
    assert in_working_form(reply, server, antiderivative=True) == server


def test_a_form_real_on_the_same_domain_takes_the_card() -> None:
    server = r"\ln\left|x - 6\right| + C"
    assert in_working_form(_reply(r"$\ln|6 - x| + C$"), server, antiderivative=True) == (
        r"\ln|6 - x| + C"
    )


def test_only_an_antiderivative_takes_the_reply_s_form() -> None:
    """Gemini on #2481: "Expand A(A + 2) + C", its C the user's own letter, certified the
    reply's (A + 1)^2 + C. Whether a card is an antiderivative is its operation's to say."""
    reply = _reply("$(A + 1)^2 + C$")
    assert in_working_form(reply, "A^{2} + 2 A + C", antiderivative=False) == "A^{2} + 2 A + C"
    # Nor is a C in the integrand a constant of integration.
    assert in_working_form(_reply("$C x + C$"), r"\frac{C x^{2}}{2} + C", antiderivative=True) == (
        r"\frac{C x^{2}}{2} + C"
    )


@pytest.mark.parametrize(
    "reply",
    [
        "**Solution**\n$u = 2x$\n\n\\[\n\\boxed{\\frac{1}{2}\\sec\\left(2x - \\frac{\\pi}{4}\\right) + C}\n\\]",
        "**Solution**\n$u = 2x$\n\n$\\boxed{\\frac{1}{2}\\sec\\left(2x - \\frac{\\pi}{4}\\right) + C}$",
    ],
)
def test_a_closing_boxed_value_is_the_reply_s_answer(reply: str) -> None:
    assert in_working_form(reply, _SEC, antiderivative=True) == (
        r"\frac{1}{2}\sec\left(2x - \frac{\pi}{4}\right) + C"
    )


def test_the_integral_block_says_it_is_an_antiderivative() -> None:
    assert _block("Integrate sec(2x - pi/4) tan(2x - pi/4) with respect to x").antiderivative
    assert not _block("Evaluate the integral of 1/x from 1 to 2").antiderivative
    assert not _block("Expand (x+2)(x-3)").antiderivative
