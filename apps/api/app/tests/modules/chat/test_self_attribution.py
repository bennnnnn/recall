"""The reply never signs its own writing; a quotation of anyone else keeps its citation."""

from __future__ import annotations

import pytest

from app.modules.chat.self_attribution import drop_self_attribution

POEM = "Rain taps the glass in silver thread,  \nand hums the city off to bed."
QUOTED = "> Rain taps the glass in silver thread,  \n> and hums the city off to bed."


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        # Live (2026-11-05): "write me a two-line poem about rain".
        (f"{QUOTED}\n>\n> — Recall", POEM),
        (f"{QUOTED}\n> — Recall", POEM),
        (f"{QUOTED}\n> – *Recall*", POEM),
        (f"{QUOTED}\n> -- recall.", POEM),
        # On a quote line a hyphen is a citation too (the phone reads it as one).
        (f"{QUOTED}\n> - Recall", POEM),
        # The citation on the line under the quote closes it; across a blank line only the
        # signature goes, and the quote stays as written.
        (f"{QUOTED}\n— Recall", POEM),
        (f"{QUOTED}\n\n— **Recall**\n\nWant a longer one?", f"{QUOTED}\n\nWant a longer one?"),
        # The poem as plain lines, signed: only the signature goes.
        (f"{POEM}\n\n— Recall", POEM),
        (f"Here's one:\n\n{QUOTED}\n> — Recall\n", f"Here's one:\n\n{POEM}\n"),
        # Inside a list item the lines keep the item's indent.
        (
            "1. A haiku:\n   > Soft rain on the roof\n   > — Recall\n2. A couplet.",
            "1. A haiku:\n   Soft rain on the roof\n2. A couplet.",
        ),
    ],
)
def test_a_reply_signed_by_the_assistant_loses_the_signature_and_its_quote(
    reply: str, expected: str
) -> None:
    assert drop_self_attribution(reply) == expected


@pytest.mark.parametrize(
    "reply",
    [
        # A quotation of anyone else keeps its card and citation.
        "> The only way to do great work is to love what you do.\n>\n> — Steve Jobs",
        "> I'm sorry, Dave. I'm afraid I can't do that.\n> — HAL 9000",
        # The name in a sentence, a title or a list item is no signature.
        "Recall can remind you tomorrow at 9.",
        "> Total recall is rare.\n> — Total Recall (1990)",
        "Memory skills:\n- Recall\n- Recognition",
        # Inside a code fence nothing changes.
        "```markdown\n> Rain.\n> — Recall\n```",
        POEM,
    ],
)
def test_other_citations_and_the_name_elsewhere_are_left_alone(reply: str) -> None:
    assert drop_self_attribution(reply) == reply


@pytest.mark.parametrize(
    "quote",
    [
        "> Be the change you wish to see in the world.\n> — Gandhi",
        "> Be the change you wish to see in the world.\n> - Gandhi",
        "> Warning: do not mix bleach and ammonia.",
    ],
)
def test_a_sign_off_apart_from_a_quote_leaves_that_quote_whole(quote: str) -> None:
    """Reviews of #2300: a sign-off after a blank line unwrapped Gandhi's card, with either
    dash, and a callout."""
    assert drop_self_attribution(f"{quote}\n\n— Recall") == quote


def test_a_sign_off_under_a_cited_quote_leaves_the_citation() -> None:
    quote = "> Be the change.\n> - Gandhi"
    assert drop_self_attribution(f"{quote}\n— Recall") == quote
