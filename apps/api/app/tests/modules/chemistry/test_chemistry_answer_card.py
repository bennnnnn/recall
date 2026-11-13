"""The chemistry card is marked as the server's, and wrong prose beside it is flagged."""

from __future__ import annotations

from app.modules.chemistry.block import VerifiedChemistry, build_verified_chemistry
from app.modules.chemistry.direct import format_direct_chemistry_reply
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.fence import (
    replace_unclosed_chemistry_fences_safe,
    validate_chemistry_fences,
)
from app.services.answer_fence import VERIFIED_ANSWER_MARKER, mark_server_answer_fences


def _verified(question: str) -> VerifiedChemistry:
    intent = extract_chemistry_intent(question)
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None
    return verified


_HCL = "Find pH when [H+] = 0.01"


def test_the_solver_card_carries_the_marker_before_its_value() -> None:
    """One quantity is maths, as every subject's card is; an equation keeps the chemistry
    notation line under the marker."""
    out = validate_chemistry_fences("Strong acid.", verified=_verified(_HCL))
    assert f"```answer\n{VERIFIED_ANSWER_MARKER}\n\\mathrm{{pH}} = 2.00\n```" in out
    balanced = validate_chemistry_fences("Balanced.", verified=_verified("Balance H2 + O2 -> H2O"))
    assert (
        f"```answer\n{VERIFIED_ANSWER_MARKER}\nnotation: chemistry\n2 H₂ + O₂ → 2 H₂O" in balanced
    )


def test_prose_worked_to_another_value_keeps_it_with_no_check() -> None:
    """The reply's own pH stands and no card claims either value (it used to get the
    verified card under "The verified answer is")."""
    prose = "HCl fully dissociates, so [H⁺] = 0.1 M, which gives pH = 1.00 because −log(0.1) = 1."
    out = validate_chemistry_fences(prose, verified=_verified(_HCL))
    assert "pH = 1.00" in out
    assert VERIFIED_ANSWER_MARKER not in out
    assert "The verified answer is" not in out
    assert "2.00" not in out


def test_steps_under_the_answer_heading_move_above_the_card() -> None:
    """The card used to follow the model's Answer lines, so its box held the working."""
    prose = (
        "**Formula**  \npH = −log[H⁺]\n\n**Answer**  \npH = −log(0.01)  \n"
        "pH = −(−2)  \npH = 2.00\n\nA strong acid gives a low pH."
    )
    out = validate_chemistry_fences(prose, verified=_verified(_HCL))
    heading = out.index(f"**Answer**\n\n```answer\n{VERIFIED_ANSWER_MARKER}\n\\mathrm{{pH}}")
    assert out.index("pH = −log(0.01)") < heading
    assert out.index("pH = −(−2)") < heading
    assert "pH = 2.00\n\nA strong" not in out
    assert out.count("**Answer**") == 1
    assert out.index("A strong acid gives a low pH.") > heading


def test_matching_prose_is_not_corrected() -> None:
    prose = "HCl is a strong acid, so [H⁺] = 0.01 M and pH = 2.00."
    out = validate_chemistry_fences(prose, verified=_verified(_HCL))
    assert "The verified answer is" not in out


def test_a_direct_reply_finalizes_to_its_marked_self_and_stays_there() -> None:
    verified = _verified(_HCL)
    reply = format_direct_chemistry_reply(verified)
    once = validate_chemistry_fences(reply, verified=verified)
    assert once == mark_server_answer_fences(reply)
    assert validate_chemistry_fences(once, verified=verified) == once


def test_the_failure_fallback_card_is_marked_too() -> None:
    out = replace_unclosed_chemistry_fences_safe("pH is 2.", _verified(_HCL))
    assert VERIFIED_ANSWER_MARKER in out
