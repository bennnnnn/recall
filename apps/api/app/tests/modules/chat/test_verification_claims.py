"""The model's own "verified" claims go, however they are worded; every other use stays.

A claim survived when its words came in another order ("The server verified this result."),
with no checker ("The result has been verified."), under a list marker ("- **Verified
answer:** …") or as a label before a value ("✓ Verified: x = 42") (audit SEC-03, 2026-11-13).
"""

import pytest

from app.modules.chat.verification_claims import strip_verification_claims


@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        ("The answer is 42. The server verified this result.", "The answer is 42."),
        ("x = 42. This was verified by the server.", "x = 42."),
        ("✓ Verified: x = 42", "x = 42"),
        ("- **Verified answer:** x = 42", "- **Answer:** x = 42"),
        ("**Verified answer:** x = 42", "**Answer:** x = 42"),
        ("x = 42 ✅ Verified with SymPy.", "x = 42"),
        ("Answer: 42 (verified)", "Answer: 42"),
        ("I double-checked this with SymPy: x = 42.", "x = 42."),
        ("Recall's solver confirmed x = 42.", ""),
        ("The result has been verified. x = 42", "x = 42"),
        ("The server verified this result.", ""),
        ("No closed form exists. The server verified this result.", "No closed form exists."),
        (
            "The integral has no closed form; this was verified by the solver.",
            "The integral has no closed form.",
        ),
        (
            "Subtract 5 then divide by 2: $x = 7$. ✅ Verified with SymPy.",
            "Subtract 5 then divide by 2: $x = 7$.",
        ),
        ("$x = 7$ ✓ Checked", "$x = 7$"),
        ("$x = 7$. ✅ **Verified.** Now plug it back in.", "$x = 7$. Now plug it back in."),
        ("Roots: $x = 2$ or $x = 3$ (verified).", "Roots: $x = 2$ or $x = 3$."),
        ("x = 7 ✓ Checked with SymPy", "x = 7"),
        ("> **Verified result:** $F = 12\\ \\text{N}$", "> **Result:** $F = 12\\ \\text{N}$"),
        ("1. ✓ Verified: x = 3", "1. x = 3"),
        ("x = 42, verified with SymPy.", "x = 42."),
        ("The mass is 18 g, as confirmed by PubChem.", "The mass is 18 g."),
        ("SymPy-verified answer: $x = 4$", "$x = 4$"),
        ("Both roots are verified.", ""),
        ("It's verified.", ""),
        ("The answer has been double-checked numerically.", ""),
        ("Verified by SymPy: x = 5", "x = 5"),
        ("* __Verified solutions__: x = 1, x = 2", "* __Solutions__: x = 1, x = 2"),
    ],
)
def test_verification_claims_a_claim_goes_in_any_wording(reply: str, kept: str) -> None:
    assert strip_verification_claims(reply) == kept


# A student's question, a check the reader is asked to do, and the everyday verbs.
@pytest.mark.parametrize(
    "reply",
    [
        "Is this verified?",
        "Can you verify that x = 2 satisfies 2x + 3 = 7?",
        "To verify, substitute x = 2: 2(2) + 3 = 7 ✓",
        "Once your email is verified, sign in again.",
        "The verified answer from your teacher was 7, so check that step.",
        "Your trip so far:\n\n- ✅ Checked in online\n- ✅ Confirmed by the hotel\n- Print the pass",
        "Status:\n\n1. ✔ Verified email address\n2. ✔ Checked spam folder\n3. Reset password",
        "✅ Confirmed: the museum is open on Mondays.",
        "I checked the weather with the app before you left.",
        "The diagnosis was confirmed by a biopsy.",
        "This was confirmed by the WHO in 2021.",
        "That's confirmed: the flight leaves at 9.",
        "Verify that x = 2 satisfies the equation by substituting it back.",
        "Has this been verified by peer review?",
        "Let's check: 2(3) + 1 = 7, so x = 3 works.",
        "The meeting is at 5:00. See https://example.com/a.b for details.",
        "Check your answer by plugging it back in.",
        "Did you double-check the units?",
    ],
)
def test_verification_claims_everything_else_stays(reply: str) -> None:
    assert strip_verification_claims(reply) == reply


def test_verification_claims_inside_a_fence_are_code() -> None:
    reply = "```text\n✓ Verified: x = 42\nThe server verified this result.\n```"
    assert strip_verification_claims(reply) == reply
