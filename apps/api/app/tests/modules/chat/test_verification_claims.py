"""The model's own "verified" claims go, however they are worded; every other use stays.

A claim survived when its words came in another order ("The server verified this result."),
with no checker ("The solution is verified: x = 42"), under a list marker ("- **Verified
answer:** …") or as a label before a value ("✓ Verified: x = 42") (audit SEC-03, 2026-11-13).
Only the claim goes, never the value beside it, and an everyday "confirmed" or "verified"
stays, a checker that is no solver ("the app") included (review, 2026-11-13). What a tool
does, code, and a check mark beside a student's line stay too, and only a turn that can show
a card is read for claims at all (second review, 2026-11-13).
"""

import contextvars
from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.core.config import Settings
from app.core.readings import begin_turn
from app.modules.chat.finalize_subjects import prepare_model_reply
from app.modules.chat.verification_claims import strip_verification_claims
from app.modules.turn_reading.plan import single_plan
from app.modules.turn_reading.turn import TurnReading, keep_turn_reading


@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        ("Step 3: verified with SymPy: x = 4", "Step 3: x = 4"),
        ("**Verified:** x = 4 and y = 2.", "x = 4 and y = 2."),
        ("x = 4. Verified.", "x = 4."),
        ("Recall's solver confirmed x = 42.", "x = 42."),
        (
            "The answer x = 42 was verified by the server and is final.",
            "The answer x = 42 is final.",
        ),
        ("The answer (verified by SymPy) is x = 42.", "The answer is x = 42."),
        ("The answer, which SymPy verified, is x = 42.", "The answer is x = 42."),
        ("x = 42 — SymPy agrees.", "x = 42."),
        ("I ran it through SymPy and got x = 42.", "x = 42."),
        ("Checked by Recall: x = 42", "x = 42"),
        ("Result verified ✅: x = 42", "x = 42"),
        ("Answer (verified): x = 42", "Answer: x = 42"),
        ("The solution is verified: x = 42", "x = 42"),
        (
            "Verification: x = 42 satisfies the equation (checked with SymPy).",
            "Verification: x = 42 satisfies the equation.",
        ),
        ("The verified result: x = 42", "The result: x = 42"),
        ("The answer is 42. The server verified this result.", "The answer is 42."),
        ("x = 42. This was verified by the server.", "x = 42."),
        ("✓ Verified: x = 42", "x = 42"),
        ("- **Verified answer:** x = 42", "- **Answer:** x = 42"),
        ("**Verified answer:** x = 42", "**Answer:** x = 42"),
        ("x = 42 ✅ Verified with SymPy.", "x = 42"),
        ("Answer: 42 (verified)", "Answer: 42"),
        ("I double-checked this with SymPy: x = 42.", "x = 42."),
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
        ("SymPy-verified answer: $x = 4$", "Answer: $x = 4$"),
        ("x = 2 or x = 3. Both roots are verified.", "x = 2 or x = 3."),
        ("x = 5. The answer has been double-checked numerically.", "x = 5."),
        ("Verified by SymPy: x = 5", "x = 5"),
        ("* __Verified solutions__: x = 1, x = 2", "* __Solutions__: x = 1, x = 2"),
        # The writer's own check, said as done, keeps its value (review, 2026-11-13).
        ("I've verified the answer: x = 6.", "x = 6."),
        ("I verified this answer by substituting it back: x = 6.", "x = 6."),
        ("The solution is verified by substitution: $2(6) + 5 = 17$.", "$2(6) + 5 = 17$."),
        ("x = 6, which I verified.", "x = 6."),
        ("Double-checked: x = 6.", "x = 6."),
        ("Confirmed: x = 6", "x = 6"),
        ("x = 6 — confirmed.", "x = 6."),
        ("x = 6 (I checked it twice).", "x = 6."),
        ("I ran it through SymPy and got the same result: x = 6.", "x = 6."),
        ("x = 6 is verified.", "x = 6."),
        ("x = 6. I confirmed it by substitution. x = 6 is verified.", "x = 6. x = 6."),
    ],
)
def test_verification_claims_a_claim_goes_and_its_value_stays(reply: str, kept: str) -> None:
    assert strip_verification_claims(reply) == kept


# A question, a check the reader is asked to do, everyday verbs, and checkers no solver.
@pytest.mark.parametrize(
    "reply",
    [
        "Verify that x = 2 satisfies the equation.",
        "Is this verified?",
        "The verified answer is x = 3.",
        "Now verify that your answer works by substituting it back.",
        "Your doctor ran the test again. The results were confirmed.",
        "The election results were confirmed by the state.",
        "Einstein predicted gravitational waves in 1916. This has been verified.",
        "Your order was confirmed by the app.",
        "I checked with the app and it's open until 9.",
        "The booking is confirmed via the app.",
        "Your answer is correct; the work has been checked.",
        "Each step was checked: first expand, then simplify.",
        "Checked: you forgot the minus sign.",
        "Verified: true is the server's line.",
        "Double-check: did you include units?",
        "Confirmed: the museum is open on Mondays.",
        "Validated: the form accepts emails.",
        "The answer has been confirmed by experiment.",
        "Make sure each value is checked before you submit.",
        "These values were confirmed in 2019 measurements.",
        "That's verified.",
        "It's been verified by many studies that exercise helps.",
        "I double-checked the time zone with the app: it's 3 pm in Tokyo.",
        "It's verified.",
        "Once your email is verified, sign in again.",
        "The verified answer from your teacher was 7, so check that step.",
        "Your trip so far:\n\n- ✅ Checked in online\n- ✅ Confirmed by the hotel\n- Print the pass",
        "Status:\n\n1. ✔ Verified email address\n2. ✔ Checked spam folder\n3. Reset password",
        "I checked the weather with the app before you left.",
        "The diagnosis was confirmed by a biopsy.",
        "This was confirmed by the WHO in 2021.",
        "That's confirmed: the flight leaves at 9.",
        "Has this been verified by peer review?",
        "Let's check: 2(3) + 1 = 7, so x = 3 works.",
        "The meeting is at 5:00. See https://example.com/a.b for details.",
        "Check your answer by plugging it back in.",
        "Did you double-check the units?",
        # What a tool or a server does is no claim about this answer (review, 2026-11-13).
        "The server checks the JWT signature before it trusts the token.",
        "The server validates the request body against the schema.",
        "Each session is checked by the server on every request.",
        "The email address was verified by the server, so the account is active.",
        "SymPy checks equality with simplify(a - b) == 0.",
        "In Python, `x = 5` sets x. SymPy verifies identities with `simplify`.",
        "SymPy verified the identity using `simplify`.",
        "A SAT solver checks whether the clauses can all be true.",
        "I ran it through SymPy and got a different result than by hand, so check the brackets.",
        "The checker validates each move before the game continues.",
        "```python\nx = 5\nprint(x)\n```\n\nAll tests pass. The results are verified.",
        "```python\nassert add(2, 3) == 5\n```\n\nThe values are checked.",
        "Run `pytest` and the results are verified: `x = 5` passes.",
        # A check mark beside a value marks a line, the student's own in "check my work".
        "Line 1: $2x + 5 = 17$ ✓\nLine 2: $2x = 12$ ✓\nLine 3: $x = 7$ ✗ (it should be 6)",
        "- x = 2: $2^2 - 4 = 0$ ✅\n- x = 3: $3^2 - 4 = 5$ ❌",
        "Your answer x = 6 is correct ✓",
        "| Step | Work | OK? |\n|---|---|---|\n| 1 | 2x = 12 | ✓ |",
        "x = 42 ✓",
        "**x = 6** ✅",
        "✅ x = 42",
        "To verify, substitute x = 2: 2(2) + 3 = 7 ✓",
        "Checked: you forgot the minus sign in 2x - 5 = 7.",
        "x = 6. Confirmed: the museum is open on Mondays.",
    ],
)
def test_verification_claims_everything_else_stays(reply: str) -> None:
    assert strip_verification_claims(reply) == reply


def test_verification_claims_inside_a_fence_are_code() -> None:
    reply = "```text\n✓ Verified: x = 42\nThe server verified this result.\n```"
    assert strip_verification_claims(reply) == reply


_PROMPT = "How does my API check its requests?"
_REPLY = "x = 42 is verified."


def _prepared(subject: str | None, reason: str, *, verified: object = None) -> str:
    begin_turn()
    keep_turn_reading(
        TurnReading(
            _PROMPT,
            True,
            single_plan(_PROMPT),
            "one_request",
            "no_cue",
            subject=subject,
            subject_reason=reason,
        )
    )
    ctx = SimpleNamespace(
        verified_subject=verified,
        solver_unverified=False,
        worked=None,
        money=None,
        user_message_content=_PROMPT,
    )
    state = SimpleNamespace(
        server_text=False, text=_REPLY, settings=Settings(), ctx=ctx, user_stopped=False
    )
    return prepare_model_reply(cast(Any, state))


@pytest.mark.parametrize(
    ("subject", "reason", "verified", "kept"),
    [
        # A coding or everyday turn shows no card: only a claim naming the checker goes there.
        (None, "code", None, _REPLY),
        (None, "none", None, _REPLY),
        # A subject's turn, a verified one, or one whose message was not read can show one.
        ("math", "math", None, "x = 42."),
        (None, "none", object(), "x = 42."),
        (None, "not_read", None, "x = 42."),
    ],
)
def test_a_claim_goes_only_on_a_turn_that_can_show_a_card(
    subject: str | None, reason: str, verified: object, kept: str
) -> None:
    out = contextvars.copy_context().run(_prepared, subject, reason, verified=verified)
    assert out == kept


# A turn that can show no card still never says the app checked it (third review, 2026-11-13).
@pytest.mark.parametrize(
    ("reply", "kept"),
    [
        ("About 384,400 km. This was verified by the server.", "About 384,400 km."),
        (
            "GPS uses timing: d = c·t. Verified with SymPy: d = 3×10^8 m.",
            "GPS uses timing: d = c·t. d = 3×10^8 m.",
        ),
        (
            "There are 86,400 seconds in a day. ✅ Verified with SymPy.",
            "There are 86,400 seconds in a day.",
        ),
        ("The answer (verified by SymPy) is x = 42.", "The answer is x = 42."),
        ("Recall's solver confirmed x = 42.", "x = 42."),
        ("x = 4, confirmed by the app.", "x = 4."),
        # Claims naming no checker are a card turn's to strip.
        ("x = 42 is verified.", "x = 42 is verified."),
        ("x = 42. ✅ Verified.", "x = 42. ✅ Verified."),
        ("**Verified answer:** x = 7", "**Verified answer:** x = 7"),
        ("Your order was confirmed by the app.", "Your order was confirmed by the app."),
        (
            "I checked with the app and it's open until 9.",
            "I checked with the app and it's open until 9.",
        ),
    ],
)
def test_a_claim_naming_the_checker_goes_on_every_turn(reply: str, kept: str) -> None:
    assert strip_verification_claims(reply, card_turn=False) == kept
