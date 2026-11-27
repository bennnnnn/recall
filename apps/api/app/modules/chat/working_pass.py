"""The working check over a reply's own working: one pure function, run in the SymPy pool.

Working the model wrote with no verified result behind it: a slip in one multiplication
carries into the answer, so it is put right and carried on, or named when it cannot be put
right in place (``working_fix``). Its final answer goes in the same card a verified one
does, without the check; each card is then the value its working's own method reaches with
the arithmetic redone (``chain_cards``), and the card is the working's last step
(``working_cards``). The card is not said again below the cards
(``worked_lead.drop_restated_tail``).

It reads every line of arithmetic and the units the working writes (Pint), so it runs off
the event loop, in the SymPy pool (``finalize_subjects.check_working``). Pure: text in, text
out.
"""

from __future__ import annotations

from app.modules.chat.chain_cards import held_to_chains
from app.modules.chat.worked_lead import drop_recap_tail, drop_restated_tail
from app.modules.chat.working_approximations import corrected_approximations
from app.modules.chat.working_cards import held_cards, held_vector_sizes, without_unbacked_senses
from app.modules.chat.working_check import working_note
from app.modules.chat.working_fix import put_right
from app.services.answer_fence import land_answer_card
from app.services.md_fence_scan import close_unclosed_fences
from app.services.part.answer_cards import land_part_answer_cards
from app.services.rounding_rule import asked_precision


def checked_working(
    text: str, question: str, *, school: bool, laid_out: bool, decimal_comma: bool
) -> str:
    """``text`` with its working put right, its cards landed and held to the working, and
    one closing note naming what was corrected or what to check (the module docstring)."""
    # A decimal given for an exact value is the server's to get right.
    text = corrected_approximations(text)
    # A wrong number in a step is put right, and the lines built on it after it; a step that
    # cannot be put right in place, or whose number is still written after it, is named.
    text, carried_note = put_right(text, question)
    note = carried_note or working_note(text, question)
    # A reply in parts gets a card under each part's Answer heading.
    text = land_part_answer_cards(text) or land_answer_card(text, None, school=school)
    # The card is the working's last step: an expression left unworked and a card that is
    # not its value (``working_cards``).
    text, card_note = held_cards(text, question)
    # Then each card is the value its working's own method reaches, worked again at full
    # precision, its units with it; a corrected card names what it corrected, in place of
    # the step's note. Last, so no arithmetic of a single step undoes a conversion it put in.
    text, corrected, claim = held_to_chains(text, question, asked_precision(question))
    text = without_unbacked_senses(held_vector_sizes(text))
    note = corrected or note or card_note
    text = drop_restated_tail(text, question, decimal_comma=decimal_comma)
    if laid_out:
        # The working said again after the cards goes (``worked_lead.drop_recap_tail``).
        text = drop_recap_tail(text, question, decimal_comma=decimal_comma)
    for line in (note, claim):
        if line:
            text = with_closing_note(text, line)
    return text


def with_closing_note(text: str, note: str) -> str:
    """``text`` with ``note`` after it, never inside a fence the reply left open: that fence
    is closed first, as the closer would close it (a card cut off at the length limit kept
    "Check the answer: …" as its last line, review of #2592)."""
    return f"{close_unclosed_fences(text).rstrip()}\n\n{note}"
