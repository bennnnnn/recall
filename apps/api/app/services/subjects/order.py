"""The subject order: which subject a line is, and which step of the order decided it.

``read_subject_reason`` is the one place the order is written (structure ticket ST-05): code
is no problem, a scanned caption is its subject's, a closed chemistry calculation is
chemistry's before physics claims its numbers, physics before maths, chemistry-shaped
questions never go to algebra, a chart of the user's own numbers is no maths, and chemistry
looks a line up last. ``services.subjects.dispatch`` reads a line's subject from it.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.core.readings import reading
from app.modules.math.tools.prompt import needs_symbolic_math
from app.modules.physics.extract import extract_physics_intent, needs_physics
from app.services.subjects.guard import first_failure
from app.services.subjects.registry import SubjectName

logger = logging.getLogger(__name__)

# Which step of the subject order decided a line (``read_subject_reason``): the order is
# the precedence, written once there.
SubjectReason = Literal[
    "code",
    "scanned",
    "chemistry_closed",
    "physics",
    "curve_to_math",
    "physics_givens",
    "chemistry_shaped",
    "math",
    "chart",
    "chemistry_off",
    "chemistry_question",
    "none",
    # Not a step of the order: no step reads the whole line, and the turn's plan is separate
    # problems a subject solves each; the turn takes its first part's subject
    # (``chat.turn_prep.reading``).
    "parts",
]


@dataclass(frozen=True)
class SubjectReading:
    """A line's subject and the step of the subject order that decided it."""

    subject: SubjectName | None
    reason: SubjectReason


def _closed_chemistry(text: str) -> bool:
    """A chemistry cue plus a complete extraction, before algebra can claim it."""
    from app.modules.chemistry.extract import extract_chemistry_intent
    from app.modules.chemistry.request import is_chemistry_question

    if not is_chemistry_question(text):
        return False
    return extract_chemistry_intent(text) is not None


# What makes a chemistry question chemistry's even when no chemistry reader closes it: a
# symbol whose case is its meaning (pH, Ka), an amount in a chemistry unit (0.10 M, 3.0 mol,
# 98 g/mol), or a compound's formula (CH3COOH, NaCl). Maths read "Ka = 1.8 x 10^-5" as an
# equation in an unknown x and "verified" x = 55555.6; the question is chemistry's even when
# chemistry can only leave it to the model.
_CHEMISTRY_SYMBOL = re.compile(
    r"(?<![A-Za-z0-9])(?:pH|pOH|pKa|pKb|Ka|Kb|Kw|Ksp|Kc|Kp|Qc)(?![A-Za-z])"
)
_CHEMISTRY_AMOUNT = re.compile(
    r"(?<![A-Za-z])(?:\d(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?\s*"
    r"(?:M|mM|mol(?:es?)?|mmol|mol/L|g/mol|mol/kg)(?![A-Za-z])"
)


def _chemistry_shaped(text: str) -> bool:
    """A chemistry question by its symbols, amounts or formulas, solved or not."""
    from app.modules.chemistry.input_text import read_chemistry_text
    from app.modules.chemistry.request import is_chemistry_question, names_compound

    if not is_chemistry_question(text):
        return False
    read = read_chemistry_text(text)
    if _CHEMISTRY_SYMBOL.search(read) or _CHEMISTRY_AMOUNT.search(read):
        return True
    if names_compound(read):
        return True
    return _chemical_equation(read)


def _chemical_equation(text: str) -> bool:
    """A reaction of real species ("2H2 + O2 -> 2H2O"), never a mapping such as "A -> B"."""
    from app.modules.chemistry.request import EQUATION_RE
    from app.modules.chemistry.species import parse_reaction

    return any(parse_reaction(match.group(1)) is not None for match in EQUATION_RE.finditer(text))


class _ReaderFailed(Exception):
    """A step's reader raised: the line is read again with its subject off."""

    def __init__(self, subject: SubjectName) -> None:
        super().__init__(subject)
        self.subject = subject


def _step(
    subject: SubjectName, name: str, claims: Callable[[], bool], off: frozenset[SubjectName]
) -> bool:
    """One step of the order, asking a subject's reader; a subject that is off claims nothing.
    A reader that raises switches its subject off for the line (``_read``). Uncaught, one
    chemistry reader raising failed every turn, "hi there" included (audit REL-01)."""
    if subject in off:
        return False
    try:
        return claims()
    except Exception as exc:
        if first_failure(subject, f"order.{name}"):
            logger.exception("subject %s.order.%s failed; reading without it", subject, name)
        else:
            logger.info("subject %s.order.%s failed again", subject, name)
        raise _ReaderFailed(subject) from exc


def _chemistry_marked(text: str) -> bool:
    """A chemistry symbol or amount in the line, read with no chemistry reader (``pH``, ``Ka``,
    ``0.10 M``)."""
    return bool(_CHEMISTRY_SYMBOL.search(text) or _CHEMISTRY_AMOUNT.search(text))


def _math_curve_request(text: str) -> bool:
    from app.modules.math.tools.school.curve_points import extract_curve_point_intent

    return extract_curve_point_intent(text) is not None


@reading(declined=None)
def read_subject_reason(
    text: str, has_image_attachment: bool, chemistry_enabled: bool
) -> SubjectReading | None:
    """A line's subject, and which step of the order decided it: a reading (``core/readings``).

    None only when the turn's pool read gave up (its declined value).
    """
    return _read(text, has_image_attachment, chemistry_enabled, frozenset())


def _read(
    text: str, has_image_attachment: bool, chemistry_enabled: bool, off: frozenset[SubjectName]
) -> SubjectReading:
    """The order, read again without each subject whose reader raises: that subject never
    has the line, and every other still reads it ("Solve 2x + 5 = 17" is maths' with
    chemistry's reader broken, review 2026-11-13). Each pass turns one more subject off."""
    while True:
        try:
            return _ordered(text, has_image_attachment, chemistry_enabled, off)
        except _ReaderFailed as failed:
            off = off | {failed.subject}


def _ordered(
    text: str, has_image_attachment: bool, chemistry_enabled: bool, off: frozenset[SubjectName]
) -> SubjectReading:
    """The order itself, step by step (``read_subject_reason``), with the subjects in ``off``
    claiming nothing."""
    from app.modules.turn_reading.coding import has_code_syntax

    # Pasted code is not a problem to solve: `for (int i = 1; i <= 3; i++)` is a
    # loop, and `n * 2` inside `nums.map` is not algebra.
    if has_code_syntax(text):
        return SubjectReading(None, "code")
    from app.services.subject_scan import confirmed_scan_reading, scanner_camera_subject

    # A subject's camera caption says "solve", which the math work-request
    # parser would claim. It is a photo plus a caption, not a math problem.
    scanned = scanner_camera_subject(text)
    if scanned is not None:
        # The photo's words, when the turn read them, decide its subject as a typed line's
        # do; the tab decides only when they name none. No subject reads biology.
        words = confirmed_scan_reading(text)
        read = _read(words, False, chemistry_enabled, off) if words else None
        if read is not None and read.subject is not None:
            return SubjectReading(read.subject, "scanned")
        if scanned == "biology":
            return SubjectReading(None, "scanned")
    if scanned == "chemistry":
        on = chemistry_enabled and "chemistry" not in off
        return SubjectReading("chemistry" if on else None, "scanned")
    if scanned == "physics":
        return SubjectReading("physics" if "physics" not in off else None, "scanned")
    # A closed chemistry calculation is chemistry's before physics claims its numbers:
    # "the mass percent of 5 g of sugar in 95 g of water" has masses physics would read.
    # The laws both subjects use (gases, Q = mcΔT, half-lives) are physics' alone, so
    # chemistry never closes on one.
    if chemistry_enabled and _step("chemistry", "closed", lambda: _closed_chemistry(text), off):
        return SubjectReading("chemistry", "chemistry_closed")
    if _step("physics", "needs", lambda: needs_physics(text), off):
        # "h = 20t - 5t^2, find the maximum height" cues physics, but it states the
        # function and asks its maximum: physics extracts nothing, calculus does.
        if _step("math", "curve", lambda: _math_curve_request(text), off) and not _step(
            "physics", "extract", lambda: extract_physics_intent(text) is not None, off
        ):
            return SubjectReading("math", "curve_to_math")
        return SubjectReading("physics", "physics")
    from app.modules.physics import is_symbol_givens_request

    # Symbol givens with units ("P = 200 W, t = 10 s, find W") are physics even
    # when no catalog law binds; algebra would read W and s as unknowns.
    if _step("physics", "givens", lambda: is_symbol_givens_request(text), off):
        return SubjectReading("physics", "physics_givens")
    # A pH, Ka or molarity question chemistry could not close is still not algebra: maths
    # would read the x of "1.8 x 10^-5" as its unknown and verify nonsense. With chemistry's
    # reader broken, its symbols and amounts still keep the line from maths, with no subject.
    if chemistry_enabled and "chemistry" in off and _chemistry_marked(text):
        return SubjectReading(None, "chemistry_shaped")
    if chemistry_enabled and _step("chemistry", "shaped", lambda: _chemistry_shaped(text), off):
        return SubjectReading("chemistry", "chemistry_shaped")
    if _step(
        "math",
        "needs",
        lambda: needs_symbolic_math(text, has_image_attachment=has_image_attachment),
        off,
    ):
        from app.modules.math.tools.extract import extract_math_intent
        from app.modules.turn_reading.chart import chart_names_no_curve

        # A scatter plot of the user's own numbers is a chart, not an unverified maths
        # turn whose note forbids drawing it ("Here's your scatter plot", and none).
        if _step("math", "chart", lambda: chart_names_no_curve(text, extract_math_intent), off):
            return SubjectReading(None, "chart")
        return SubjectReading("math", "math")
    if not chemistry_enabled:
        return SubjectReading(None, "chemistry_off")
    from app.modules.chemistry.request import is_chemistry_question

    if _step("chemistry", "question", lambda: is_chemistry_question(text), off):
        return SubjectReading("chemistry", "chemistry_question")
    return SubjectReading(None, "none")
