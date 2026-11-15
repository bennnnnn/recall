"""Physics-owned prompt augmentation and verified-solve boundary."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Literal

from app.core.config import Settings
from app.modules.physics.block import _build_physics_block
from app.modules.physics.chain_solve import solve_chain
from app.modules.physics.extract import extract_physics_intent, needs_physics
from app.modules.physics.parts import answers_part_of, asks_count
from app.modules.physics.reply_policy import PHYSICS_PARTIAL_POLICY, PHYSICS_REPLY_POLICY
from app.modules.physics.split_parts import solve_in_parts
from app.services.latex_markup import without_markup
from app.services.solving import VerifiedPhysicsBlock, wrap_verified_physics
from app.services.workout import PHYSICS_WORKOUT_PARTS_PROMPT, SELF_CHECK_PROMPT_RULE

logger = logging.getLogger(__name__)


def _unverified_physics_note() -> str:
    return (
        "Physics note: a physics request was detected, but no complete verified "
        "solver result is available. Do not claim verification or drop units. "
        "Still finish under Answer with the result and units in inline math. "
        "Never end on the Answer heading. If there is no unique result, say "
        "what is missing instead of leaving Answer blank. Do not emit answer, "
        "graph, or simulation fences.\n\n"
        f"{PHYSICS_REPLY_POLICY} {PHYSICS_WORKOUT_PARTS_PROMPT}\n\n"
        "No verified numbers were produced for this request, so the copy-verified "
        "rule does not apply. Compute the result and write it under Answer. "
        f"{SELF_CHECK_PROMPT_RULE}"
    )


def _no_answer_note(reason: str) -> str:
    """A question that states a value no such quantity takes has no answer as written: the
    reply says why and works nothing out (``out_of_range``)."""
    return (
        f"Physics note: the question as written has no answer. {reason} Say so plainly in "
        "the reply's first line, as a fact about the question, and work out no result from "
        "it: no Given, Solution or Answer, and no ```worked block. This replaces the rule to "
        "finish under Answer. Ask which value they meant when one is likely, such as a minus "
        "sign typed by mistake. Do not emit answer, graph, or simulation fences."
    )


def _sign_check_note(reason: str) -> str:
    """The question's law, filled with its values as signed, gives a result no such quantity
    takes. Its signs may only mark directions, so the reply checks them before it answers."""
    return (
        f"{_unverified_physics_note()}\n\nPhysics sign check: {reason} Check the signs the "
        "question states before you answer. When they make it impossible as written (a force "
        "said to point against the acceleration it gives), say so plainly and work out no "
        "result. When they only mark directions (a braking force given as a size beside a "
        "deceleration written negative), answer with sizes and say so."
    )


PhysicsOutcome = Literal["skip", "note", "failed", "symbolic", "verified", "picture"]


@dataclass(frozen=True)
class NoAnswer:
    """Why a declined question has no answer as written, as the note the prompt carries."""

    note: str
    # The question states the value itself (a -5 Ω resistor): the reply works nothing out.
    # A result is only as signed as the reader read it, and may be answered with sizes.
    stated: bool


def solve_physics_request(
    user_content: str, settings: Settings, needs_subject: bool | None
) -> tuple[PhysicsOutcome, VerifiedPhysicsBlock | None]:
    """Read a physics request and solve it, in the SymPy pool (never on the event loop).

    ``skip``: not physics. ``note``: physics with no template, so the prompt note.
    ``failed``: a template matched and its solve failed. ``symbolic`` and ``verified``
    carry the block; ``picture`` carries a free-body diagram and no result ("draw the
    forces on a box on a 30° incline" names no mass and no μ).
    """
    detected = needs_physics(user_content) if needs_subject is None else needs_subject
    if not detected:
        return "skip", None
    from app.modules.physics.symbolic.request import (
        is_symbolic_physics_request,
        parse_symbolic_physics_request,
    )

    if is_symbolic_physics_request(user_content):
        request = parse_symbolic_physics_request(user_content)
        if request is None:
            return "note", None
        from app.modules.physics.symbolic.solver import build_symbolic_physics_block

        try:
            return "symbolic", build_symbolic_physics_block(request, user_content)
        except Exception:
            logger.info("symbolic physics model declined", exc_info=True)
            return "failed", None
    intent = extract_physics_intent(user_content)
    read_text = user_content
    # The parts and asks a LaTeX paste holds are its plain text's (``latex_markup``).
    user_content = without_markup(user_content)
    block: VerifiedPhysicsBlock | None = None
    if intent is not None:
        try:
            block = _build_physics_block(intent, settings, [])
        except Exception:
            logger.warning("physics solve failed for kind=%s", intent.kind, exc_info=True)
    # A question that asks more than one law answered, or that no one law answered: every
    # ask by its own law, laws chained (``chain_solve``), else each part read alone.
    if block is None or (len(block.physics_parts) < 2 and asks_count(user_content) > 1):
        block = _more_answered(block, user_content, settings)
    if block is None:
        return _picture_or(user_content, "note" if intent is None else "failed")
    partial = answers_part_of(user_content, block.physics_intent, len(block.physics_parts))
    return "verified", replace(
        block, text=wrap_verified_physics(block.text), partial=partial, read_text=read_text
    )


def solve_or_say_why(
    user_content: str, settings: Settings, needs_subject: bool | None
) -> tuple[PhysicsOutcome, VerifiedPhysicsBlock | None, NoAnswer | None]:
    """``solve_physics_request``, and for a question it declines, why the question has no
    answer as written when its values say so (``out_of_range``), in the same pool call."""
    outcome, block = solve_physics_request(user_content, settings, needs_subject)
    if outcome not in ("note", "failed"):
        return outcome, block, None
    from app.modules.physics.out_of_range import result_out_of_range, stated_out_of_range

    stated = stated_out_of_range(user_content)
    if stated is not None:
        return outcome, None, NoAnswer(_no_answer_note(stated), stated=True)
    result = result_out_of_range(user_content)
    if result is not None:
        return outcome, None, NoAnswer(_sign_check_note(result), stated=False)
    return outcome, None, None


def _more_answered(
    block: VerifiedPhysicsBlock | None, user_content: str, settings: Settings
) -> VerifiedPhysicsBlock | None:
    """The first of the chain and the part-by-part solve that answers more of the question
    than ``block``: any answer where there was none, else more parts. The same question
    answered again by another law keeps the first answer."""
    answered = 0 if block is None else max(len(block.physics_parts), 1)
    for solve in (solve_chain, solve_in_parts):
        found = solve(user_content, settings)
        if found is not None and max(len(found.physics_parts), 1) > answered:
            return found
    return block


def _picture_or(
    user_content: str, outcome: PhysicsOutcome
) -> tuple[PhysicsOutcome, VerifiedPhysicsBlock | None]:
    """Nothing solved, but the forces it asks to see can still be drawn."""
    from app.modules.physics.force_pictures import force_picture_block

    block = force_picture_block(user_content)
    return ("picture", block) if block is not None else (outcome, None)


async def build_physics_augmentation(
    user_content: str,
    settings: Settings,
    *,
    needs_subject: bool | None = None,
) -> tuple[str | None, VerifiedPhysicsBlock | None, bool, bool]:
    """Build physics context without passing through math extraction or blocks.

    The third value is true only when a matching template was solved and that
    solve failed, or the question has no answer as written. A physics question with
    no template still gets the prompt note, and it is not reported as a failed check.
    The fourth is true when the question states a value no such quantity takes: the
    reply works nothing out (``SubjectAugmentation.unanswerable``).
    """
    if not settings.physics_enabled:
        return None, None, False, False
    from app.core.sympy_executor import run_sympy

    try:
        outcome, block, no_answer = await run_sympy(
            solve_or_say_why,
            user_content,
            settings,
            needs_subject,
            timeout=settings.stem_solve_timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            "physics read and solve timed out after %ss", settings.stem_solve_timeout_seconds
        )
        return _unverified_physics_note(), None, True, False
    except Exception:
        logger.warning("physics read and solve failed", exc_info=True)
        return _unverified_physics_note(), None, True, False
    if outcome == "skip":
        return None, None, False, False
    if no_answer is not None:
        return no_answer.note, None, True, no_answer.stated
    if outcome == "note":
        return _unverified_physics_note(), None, False, False
    if outcome == "picture" and block is not None:
        return block.text, block, False, False
    if block is None:
        return _unverified_physics_note(), None, True, False
    policy = (
        f"{PHYSICS_REPLY_POLICY}\n\n{PHYSICS_PARTIAL_POLICY}"
        if block.partial
        else PHYSICS_REPLY_POLICY
    )
    return f"{block.text}\n\n{policy}", block, False, False
