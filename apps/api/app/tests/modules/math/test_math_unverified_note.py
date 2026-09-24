"""The "couldn't verify" note only belongs on a reply that contains math.

turn_prep marks a turn ``math_unverified`` whenever a math block was injected
and SymPy then produced nothing, so *every* extractor false positive reaches
the stamp. Reported from the app: a chat about anatomy, the user typed "show
me", and the reply ended with *Couldn't verify this with SymPy.*

Fixing each false positive one at a time never ends. Guarding the stamp makes
the whole class fail quietly: a misfire leaves the reply alone instead of
putting a SymPy footer under prose.
"""

from __future__ import annotations

import pytest

from app.modules.math.fence import append_unverified_math_note

NOTE = "*Couldn't verify this with SymPy.*"


@pytest.mark.parametrize(
    "content",
    [
        "A vagina is an internal part of the female reproductive anatomy.",
        "Uterus | Cervix | Vagina | Vaginal opening / Vulva",
        "- Vulva: outside genital area\n- Cervix: opening between vagina and uterus",
        "I cannot show explicit images.",
    ],
)
def test_note_is_not_stamped_on_a_reply_with_no_math(content: str) -> None:
    assert append_unverified_math_note(content) == content


@pytest.mark.parametrize(
    "content",
    [
        "The answer is $x = 5$.",
        "So 2+2 = 4 overall.",
        "We get x = 12 at the end.",
        r"It is \frac{1}{2} of the total.",
        "```answer\nx = 2\n```",
        "```graph\n{}\n```",
        # A verified-physics answer carries no operator at all. An earlier,
        # cleverer version of the guard looked for one and dropped the note
        # from exactly this shape of reply.
        "The mass is 12 kg.",
    ],
)
def test_note_is_still_stamped_when_the_reply_holds_math(content: str) -> None:
    """A real math reply that SymPy could not confirm must still say so."""
    out = append_unverified_math_note(content)

    assert out.endswith(NOTE)
    assert content.rstrip() in out


def test_a_bare_number_in_prose_keeps_the_note() -> None:
    """Deliberate conservatism, not an oversight.

    "You have 3 options" is not math, but telling it apart from "12 kg" needs
    to understand the sentence. Stamping it is what happened before this guard
    existed, so erring that way costs nothing; erring the other way would hide
    the note on a real answer.
    """
    assert NOTE in append_unverified_math_note("You have 3 options here.")


def test_note_is_not_duplicated() -> None:
    once = append_unverified_math_note("2 + 2 = 4")
    assert append_unverified_math_note(once) == once
    assert once.count(NOTE) == 1
