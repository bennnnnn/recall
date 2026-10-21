"""Finalize passes that keep the answer card the server's.

The model's reply is prepared first: it cannot forge the server's check. Then the
subject that verified the turn checks the reply's fences against its block
(chemistry and physics by their own ``fence.py``; maths owns every other reply),
and the reply gets the notes and the working check an unverified answer needs.
``chat/finalize_passes.py`` lists these passes in order.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypeGuard

from app.core import sympy_executor
from app.modules.chemistry import fence as chemistry_fence
from app.modules.chemistry.context import append_unverified_chemistry_note
from app.modules.math.fence import append_unverified_math_note
from app.modules.math.text_plot import strip_text_plots_on_graph_turn
from app.modules.physics import fence as physics_fence
from app.services.answer_fence import (
    demote_answer_fences,
    land_answer_card,
    mark_server_answer_fences,
    normalize_owned_fences,
    strip_forged_verified_markers,
    strip_model_simulation_fences,
    strip_verification_claims,
)
from app.services.solving import (
    VerifiedMathBlock,
    VerifiedPhysicsBlock,
    VerifiedSolveBlock,
    strip_verified_solve_markers,
)
from app.services.working_check import is_worked_solution, working_note

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

logger = logging.getLogger(__name__)


def fallback_text(raw: str, *, server_text: bool) -> str:
    """What persists when finalizing fails: never a check the server did not write."""
    try:
        if server_text:
            return mark_server_answer_fences(raw)
        return strip_forged_verified_markers(raw)
    except Exception:
        logger.exception("answer-card fallback failed; dropping marker lines")
        lines = raw.split("\n")
        return "\n".join(line for line in lines if "verified" not in line.lower())


def prepare_model_reply(state: FinalizeState) -> str:
    """Model text before any server card is added to it.

    The model cannot forge the server's ``verified: true`` line, every spelling
    of its answer fences is put in the one form the subject passes demote, and
    its own "✅ Verified with SymPy" claims go: on an unverified turn they fake
    the check, and on a verified one the card says it (a claim beside a wrong
    value would contradict it). A ```simulation scene is solver-sampled, so the
    model's own never ships; a verified physics turn replaces it in its pass.
    """
    if state.server_text:
        return state.text
    text = normalize_owned_fences(strip_forged_verified_markers(state.text))
    text = strip_verification_claims(text)
    if not isinstance(state.ctx.verified_subject, VerifiedPhysicsBlock):
        text = strip_model_simulation_fences(text)
    return text


def _chemistry_verified(verified: VerifiedSolveBlock | None) -> bool:
    return verified is not None and verified.subject == "chemistry"


def check_chemistry_fences(state: FinalizeState) -> str:
    """Chemistry answer text is not algebra: the maths rewrite would read its
    formulas and slash-units as expressions, so chemistry checks its own turns."""
    verified = state.ctx.verified_subject
    if not _chemistry_verified(verified):
        return state.text
    # The server never corrects its own text: only model prose can state a value
    # that differs from the verified one.
    return chemistry_fence.validate_chemistry_fences(
        state.text, verified=verified, correct=not state.server_text
    )


def recover_chemistry_fences(state: FinalizeState) -> str:
    return chemistry_fence.replace_unclosed_chemistry_fences_safe(
        state.text, state.ctx.verified_subject
    )


def _physics_block(state: FinalizeState) -> VerifiedPhysicsBlock | None:
    verified = state.ctx.verified_subject
    return verified if isinstance(verified, VerifiedPhysicsBlock) else None


def check_physics_fences(state: FinalizeState) -> str:
    verified = _physics_block(state)
    if verified is None:
        return state.text
    return physics_fence.validate_physics_fences(
        state.text, verified=verified, correct=not state.server_text
    )


def recover_physics_fences(state: FinalizeState) -> str:
    return physics_fence.replace_unclosed_physics_fences_safe(state.text, _physics_block(state))


def _math_owns(verified: VerifiedSolveBlock | None) -> TypeGuard[VerifiedMathBlock | None]:
    """Maths checks every reply chemistry or physics did not verify; the block is maths'."""
    return not _chemistry_verified(verified) and not isinstance(verified, VerifiedPhysicsBlock)


async def check_math_fences(state: FinalizeState) -> str:
    verified = state.ctx.verified_subject
    if not _math_owns(verified):
        return state.text
    math_fence = state.deps.math_fence
    if state.server_text:
        # Two solved problems have no single verified subject. Their answer
        # fences are the results. The unverified rewrite unwraps every
        # ```answer, which printed "notation: chemistry" and raw LaTeX under
        # the reply.
        if verified is None:
            return state.text
        # Direct verified replies already carry ```answer. Running that rewrite
        # on the SymPy pool can queue behind an integral for no benefit — keep
        # it in-process.
        return math_fence.validate_math_fences_worker(state.text, verified, False)
    if not math_fence.needs_math_fence_validate(state.text, verified):
        return state.text
    if state.on_status is not None:
        # The reply has streamed; this check (up to the SymPy timeout) runs
        # before it saves, while the phone still shows it as working.
        await state.on_status("checking")
    # Through the module: tests swap the SymPy pool for an inline runner there.
    return await sympy_executor.run_sympy(
        math_fence.validate_math_fences_worker,
        state.text,
        verified,
        timeout=state.settings.math_solve_timeout_seconds,
    )


def recover_math_fences(state: FinalizeState) -> str:
    """The maths rewrite did not run, so the model's own answer fences are
    demoted here (no solver needed): a timed-out pool must not let a model's
    ```answer through as a card. Wholly server text keeps its cards.
    """
    verified = state.ctx.verified_subject
    canonical = verified.canonical_fence if verified is not None else None
    text = state.deps.math_fence.replace_unclosed_graph_fence_safe(state.text, canonical)
    if state.server_text:
        return text
    return demote_answer_fences(text)


def mark_server_cards(state: FinalizeState) -> str:
    if not state.server_text:
        return state.text
    return mark_server_answer_fences(state.text)


def append_unverified_notes(state: FinalizeState) -> str:
    """Every reply, checked or not, gets the maths note when it needs one: the
    check mark is the only signal. A declined chemistry solve gets its own."""
    text = append_unverified_math_note(state.text)
    ctx = state.ctx
    if ctx.solver_unverified is True and ctx.unverified_subject == "chemistry":
        text = append_unverified_chemistry_note(text)
    return text


def check_working(state: FinalizeState) -> str:
    """Working the model wrote with no verified result behind it: a slip in one
    multiplication carries into the answer, so name the first one. Its final
    answer goes in the same card a verified one does, without the check.
    """
    ctx = state.ctx
    text = state.text
    if state.server_text or ctx.verified_subject is not None or state.was_cancelled:
        return text
    if ctx.solver_unverified is True or is_worked_solution(text):
        note = working_note(text)
        text = land_answer_card(text, None)
        if note:
            text = f"{text.rstrip()}\n\n{note}"
    return text


def strip_text_plots(state: FinalizeState) -> str:
    """A graph drawn in text characters on a graph turn: the prompt forbids it,
    and the phone shows it as broken rows of symbols."""
    ctx = state.ctx
    return strip_text_plots_on_graph_turn(
        state.text, ctx.user_message_content, ctx.verified_subject
    )


def strip_solve_markers(state: FinalizeState) -> str:
    """Prompt scaffolding must never survive into the reply. The model is told
    not to mention a system block, but instruction is not enforcement — this is
    the enforcement."""
    return strip_verified_solve_markers(state.text)


async def enrich_chemistry_fences(state: FinalizeState) -> str:
    text = state.text
    lowered = text.lower()
    if not state.settings.chemistry_enabled or (
        "```smiles" not in lowered and "```chemistry" not in lowered
    ):
        return text
    return await sympy_executor.run_sympy(
        chemistry_fence.enrich_chemistry_fences_worker,
        text,
        timeout=state.settings.math_solve_timeout_seconds,
    )
