"""The turn's read, applied before the reply's call: Auto's lane, the thinking, the layout.

The read (``chat.turn_decision``) starts when the turn loads and answers in about a second.
The turn's lane was chosen by word rules then, and the prep ran beside the read; by the
reply's call the read says the subject and how hard the question is. Its answer replaces
the rules' (``model_routing.decided``):

- the thinking level follows the effort, question by question (maths, physics and
  chemistry think only when the read calls them hard);
- Auto's lane follows the subject and the effort through catalog data;
- a maths, physics or chemistry calculation no solver verified gets the ```worked block's
  contract, as one the subject readers recognised does, when the readers missed it; a
  message the read says works nothing out loses the contract the readers gave it for its
  number ("Translate the algebraic expression 7x in different word phrases");
- a message the read calls an answer to the last reply, or a change to what the
  conversation is about, gets a note beside it saying so (``FOLLOW_NOTES``), whatever its
  subject: "the language" after "Python the language, or the snake?" was asked back on
  every try without it; and a short line the follow-up read ties to an earlier message gets
  that message, and the part or step it names (``follow_up_read``);
- an answer to the practice cards the last reply ended on (the option the read says it
  gives) is graded by the server against each card, with no ```worked layout of its own
  (``quiz_verdict_note``); one answer to several cards that says not which is asked about
  (``QUIZ_WHICH_NOTE``); a question that names an option ("why is 18 wrong?") is answered,
  ungraded, and a reply to the card that answers nothing ("is it 35 or 52?") is talked
  through, never laid out as a calculation; and an
  answer to a lesson's card or a message the read says goes on gets the next lesson's
  contract (``lesson_next_contract``). On such a turn the reply waits for the read.

Numbers a server path already worked keep their lane and their level (a verified solve, a
money card): the model only presents them. A lesson's step stays quick, a regenerate or a
disputed answer keeps its escalation, a model the user picked keeps its model. A turn that
waited for the read to search (``reply_calls.search_the_live_read``) has it already; one
that did not waits for it as long as a search would, and only when the answer could move
its lane. With no answer in time the word rules stand. Each turn's trace says which
decided (``turn_trace.note_decision``).
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any

from app.core.config import Settings
from app.modules.billing import plan as plan_service
from app.modules.billing.entitlements import has_strong_everyday_model
from app.modules.chat.decider_read import NO_ANSWER, OTHER_ANSWER, READ_SUBJECTS
from app.modules.chat.drawing_turn import ask_for_a_drawing
from app.modules.chat.drawn_picture import app_draws, solve_draws
from app.modules.chat.follow_up_read import note_the_follow_up
from app.modules.chat.json_output import is_json_request
from app.modules.chat.lesson_again import lesson_again
from app.modules.chat.model_routing.decided import decided_lane, decided_level, math_backups
from app.modules.chat.model_routing.thinking import (
    resumes_a_cut_off_reply,
    thinks_through_parts,
)
from app.modules.chat.prompt_constants.conversation import FOLLOW_NOTES
from app.modules.chat.prompt_constants.lesson_flow import LESSON_ASIDE_NOTE, lesson_next_contract
from app.modules.chat.prompt_constants.list_reference import OPTION_PICK_MARK
from app.modules.chat.prompt_constants.practice import QUIZ_WHICH_NOTE, quiz_verdict_note
from app.modules.chat.prompt_format import without_confirmation_hints
from app.modules.chat.prompt_inject import inject_before_last_user
from app.modules.chat.prompt_sections import with_problem_pictures
from app.modules.chat.quiz_cards import PracticeCard, last_reply_cards, option_letter
from app.modules.chat.turn_decision import TurnDecision, turn_decision_result
from app.modules.chat.turn_prep.reading import plan_of
from app.modules.chat.turn_trace import note_decision, note_prompt_rule, note_route
from app.modules.chat.worked_turn import (
    states_a_quantity,
    with_worked_contract,
    without_worked_contract,
    worked_layout,
)
from app.modules.turn_reading.lesson_flow import (
    active_lesson_step,
    lesson_teaches_words,
    outline_awaits_pick,
)
from app.modules.turn_reading.school_question import is_school_exercise
from app.services.md_fence_scan import line_fences
from app.services.picture_copy import DRAWN_PICTURE_NOTE

if TYPE_CHECKING:
    from app.modules.chat.turn_prep.context import StreamContext

# The question an answer answers: the last one the reply asked, read from its end. "To eat"
# after "Here's a random one: **Why do cats purr?** … Take a guess" got restaurants on 2 of
# 3 tries told only that it answered the last reply (2026-11-15).
_QUESTION = re.compile(r"[^\n.!?:]*\?")
_MARKUP = re.compile(r"[*_`]+")
# An emoji or a mark before the question's first word.
_LEAD = re.compile(r"^[^\w\"'(]+")
_QUESTION_TAIL = 800
_QUESTION_CHARS = 200


def _asked_question(reply: str) -> str | None:
    """The last question ``reply`` asked outside its fences (a sources card comes after it)."""
    prose = "\n".join(
        line
        for line, owner in zip(reply.split("\n"), line_fences(reply), strict=False)
        if owner is None
    )
    tail = _MARKUP.sub("", prose.rstrip()[-_QUESTION_TAIL:])
    found = [_LEAD.sub("", m.group(0)).strip() for m in _QUESTION.finditer(tail)]
    found = [q for q in found if len(q.split()) >= 2 and len(q) <= _QUESTION_CHARS]
    return found[-1] if found else None


# The most of an option's words a verdict quotes (a card is the model's text).
_OPTION_CHARS = 120


async def decide_from_the_read(ctx: StreamContext, settings: Settings) -> None:
    """The read's answer, applied to the turn; the word rules' choices when it has none."""
    # One wait for the read, shared by Auto's lane and a picture's contract.
    deadline = asyncio.get_running_loop().time() + settings.live_read_wait_seconds
    read = await _the_read(ctx, settings)
    # A maths picture the message asks to see: the reply describes it (``drawing_turn``).
    await ask_for_a_drawing(ctx, settings, read, deadline)
    _leave_the_picture(ctx, settings, read)
    # "explain step 2", "and b?": which message, and which part, the line follows.
    await note_the_follow_up(ctx, settings, deadline)
    if read is None or read.effort is None:
        note_decision("rules")
        return
    note_decision(
        "read",
        subject=read.subject,
        effort=read.effort,
        picture=read.picture,
        follow=read.follow,
        work=None if read.work is None else ("yes" if read.work else "no"),
    )
    ctx.thinking = _level(ctx, read)
    _follow_the_lane(ctx, settings, read)
    answered = _answered(ctx, read)
    # One answer the read places on several cards ("B" after three): which is it for?
    unplaced = len(answered) > 1 and read.unplaced is True
    _goes_on_with_the_lesson(ctx, read, answered, unplaced=unplaced)
    if _grades_the_card(ctx, answered, unplaced=unplaced):
        return
    if _replies_to_the_card(ctx, read):
        _without_worked_layout(ctx)
    else:
        _worked_layout(ctx, settings, read)
    _follow_note(ctx, read)


def _leave_the_picture(ctx: StreamContext, settings: Settings, read: TurnDecision | None) -> None:
    """A picture the app draws (``drawn_picture.app_draws``): a multi-part message's picture
    part is the problem's, and its contract says so (``with_problem_pictures``); when the
    solve drew it, the reply gives it no section or words and never places it. Otherwise the
    painting or photo asked for stays, and nothing says the app draws it.

    What the prompt was told is what finalize does (``ctx.problem_picture``): a photo or a
    painting the prompt still asked for is never taken away because the read came in later."""
    ctx.problem_picture = app_draws(read, ctx.verified_subject)
    if read is None or not ctx.problem_picture:
        return
    ctx.prompt_messages = with_problem_pictures(
        ctx.prompt_messages, plan_of(ctx.user_message_content or "", settings)
    )
    if not solve_draws(ctx.verified_subject, read.picture):
        return
    note_prompt_rule("drawn_picture")
    ctx.prompt_messages = inject_before_last_user(ctx.prompt_messages, DRAWN_PICTURE_NOTE)


async def _the_read(ctx: StreamContext, settings: Settings) -> TurnDecision | None:
    """The read when it is in; waited for only when it could still move Auto's lane, the
    layout, a picture part, or grade a card."""
    task = ctx.live_read
    if task is None:
        return None
    if task.done():
        if task.cancelled() or task.exception() is not None:
            return None
        return task.result()
    if not (
        _lane_may_move(ctx)
        or _layout_at_stake(ctx)
        or _reads_the_cards(ctx)
        or _picture_at_stake(ctx, settings)
    ):
        return None
    return await turn_decision_result(task, settings)


def _picture_at_stake(ctx: StreamContext, settings: Settings) -> bool:
    """A multi-part message with a picture or photo part: the read says whether it is the
    problem's, for the app to draw, and the prompt and finalize take the same answer (PR #2467
    review: unwaited, a verified solve's prompt asked for a photo finalize then dropped)."""
    if ctx.instant_reply is not None:
        return False
    return bool(plan_of(ctx.user_message_content or "", settings).of_kind("image", "photo"))


def _answered_window(ctx: StreamContext) -> list[Any]:
    """The window the message answers, as the read saw it: on a regenerate, without the reply
    being redone (``RegenerateTurn.before_line``). Lesson 1's card, "b", then a regenerate of
    Lesson 2: graded against Lesson 2's options, with Lesson 3 asked for (review of #2456)."""
    recent = list(ctx.recent_messages or [])
    backup = ctx.regenerate_backup
    if backup is None:
        return recent
    return [message for message in recent if getattr(message, "id", None) != backup.message_id]


def _reads_the_cards(ctx: StreamContext) -> bool:
    """The last reply ended on practice cards or a lesson: the read says which option the
    message gives, which the server grades, and whether it goes on, which the lesson follows.
    Not waited for, "b" went ungraded whenever the read came in after the prep (review,
    2026-11-14); late past the reply's wait, the system prompt's lesson steps stand."""
    if ctx.instant_reply is not None:
        return False
    recent = _answered_window(ctx)
    return bool(last_reply_cards(recent)) or active_lesson_step(recent) is not None


def _layout_at_stake(ctx: StreamContext) -> bool:
    """The readers gave the turn the ```worked contract for its number and nothing verified it:
    the read's ``work`` may take it away, whatever model or escalation the turn keeps."""
    return ctx.worked is not None and not _worked(ctx) and ctx.instant_reply is None


def _worked(ctx: StreamContext) -> bool:
    """A server path worked the numbers: a verified solve (maths, physics, chemistry, or a
    tool's), or a money turn, whose calculator card holds them."""
    return ctx.verified_subject is not None or ctx.money is not None


def _lane_may_move(ctx: StreamContext) -> bool:
    """The one test of whether the read may move Auto's lane, and so whether the turn waits
    for it. A lesson keeps its quick lane (``route``'s "lesson"), small talk has nothing to
    move, a photo turn keeps the model that reads it, a JSON ask its model with JSON mode;
    a regenerate or a dispute keeps its escalation, a model the user picked their pick."""
    return (
        ctx.auto_routed
        and ctx.user is not None
        and not _worked(ctx)
        and ctx.instant_reply is None
        and not ctx.terminal_image_content
        and ctx.thinking != "escalate"
        and not ctx.lightweight_turn
        and active_lesson_step(ctx.recent_messages) is None
        and not _shows_a_picture(ctx)
        and not is_json_request(ctx.user_message_content)
    )


def _level(ctx: StreamContext, read: TurnDecision) -> bool | str:
    """The thinking level: the read's effort, except where the turn's own state decides."""
    if ctx.thinking == "escalate" or _worked(ctx):
        return ctx.thinking
    if active_lesson_step(ctx.recent_messages) is not None:
        # A lesson under way keeps its steps quick (``route``'s "lesson").
        return "off"
    if not thinks_through_parts(ctx.user_message_content) or resumes_a_cut_off_reply(
        ctx.user_message_content, ctx.recent_messages, asked=read.resumes
    ):
        return "off"
    return decided_level(read.subject, read.effort or "none")


def _follow_the_lane(ctx: StreamContext, settings: Settings, read: TurnDecision) -> None:
    """Auto's lane for the read's subject and effort, where it may move (``_lane_may_move``)."""
    if not _lane_may_move(ctx) or ctx.user is None or read.subject is None:
        return
    pool = plan_service.model_pool(ctx.user, settings)
    lane = decided_lane(
        read.subject,
        read.effort or "none",
        pool,
        cooling=ctx.cooling_models,
        strong_everyday=has_strong_everyday_model(ctx.user, settings),
        math_lane=plan_service.math_lane_for(ctx.user, settings),
    )
    if lane is None:
        return
    note_route(f"read.{read.subject}.{read.effort}")
    # A STEM lane's own backup first (GLM), then the rules' model, then the pool's order.
    first = [*math_backups(read.subject, lane, pool, ctx.cooling_models), ctx.model]
    backups = [alias for alias in dict.fromkeys([*first, *ctx.fallback_models]) if alias != lane]
    ctx.model, ctx.fallback_models = lane, backups


def _shows_a_picture(ctx: StreamContext) -> bool:
    return any(
        isinstance(message.get("content"), list)
        for message in ctx.prompt_messages
        if isinstance(message, dict)
    )


def _worked_layout(ctx: StreamContext, settings: Settings, read: TurnDecision) -> None:
    """The ```worked contract for a calculation the subject readers missed and the read
    calls maths, physics or chemistry (P16, a resistor problem, 2026-11-10: no reader
    claimed it, so the everyday prompt answered it); a message the read says works nothing
    out gets none, and loses the one the readers gave it for a number in it. A message a
    subject's solver read and declined was not missed: its readers laid it out, and one with
    no answer as written ("a -5 Ω resistor") gets no block (``turn_prep.augment``)."""
    if _worked(ctx) or ctx.instant_reply:
        return
    if read.work is False:
        _without_worked_layout(ctx)
        return
    # The read's subject, by the registry's name.
    subject = READ_SUBJECTS.get(read.subject or "")
    if subject is None or ctx.worked is not None or ctx.solver_unverified:
        return
    content = ctx.user_message_content
    # A value to work with, not only a digit: "Name this compound: CH3CH2CH2OH" got a Given
    # and a Required for its formula (live, 2026-11-10). The read's work only takes a layout
    # away, never adds one the rules would not: a lesson's pick ("2") stays plain.
    if not (states_a_quantity(content) or is_school_exercise(content)):
        return
    layout = worked_layout(
        content,
        subject,
        settings,
        answered=False,
        lightweight=ctx.lightweight_turn,
        several_requests=plan_of(content, settings).multi,
    )
    if layout is not None:
        ctx.worked = layout
        ctx.prompt_messages = with_worked_contract(ctx.prompt_messages, layout)


def _goes_on_with_the_lesson(
    ctx: StreamContext,
    read: TurnDecision,
    answered: list[tuple[PracticeCard, str]],
    *,
    unplaced: bool,
) -> None:
    """A message that answers a lesson's card, or that the read says asks to go on ("ok
    next"), gets the next lesson's contract beside it. A yes to another offer, a pick among
    the choices the reply offered, or a question, one naming an option included ("why is 18
    wrong?"), gets a note to do that instead: "the first one", after "Want to try a harder
    one, or move on to ions?", was graded "Correct!" and Lesson 2 followed (review,
    2026-11-14). An answer whose card is asked about first starts nothing."""
    recent = _answered_window(ctx)
    number = active_lesson_step(recent)
    # "Let's start with lesson 1", the lesson just above, is pointed to (``lesson_again``).
    if number is None or unplaced:
        return
    if lesson_again(ctx.user_message_content or "", recent):
        return
    named = any(pick != NO_ANSWER for pick in read.card_picks or [])
    if answered or (read.goes_on and not named):
        note_prompt_rule("read.lesson_next")
        note = lesson_next_contract(number, words=lesson_teaches_words(recent))
    elif named or read.goes_on is False:
        note_prompt_rule("read.lesson_aside")
        note = LESSON_ASIDE_NOTE
    else:
        return
    ctx.prompt_messages = inject_before_last_user(ctx.prompt_messages, note)


def _answered(ctx: StreamContext, read: TurnDecision) -> list[tuple[PracticeCard, str]]:
    """Each card of the last reply the message answers, with the option the read says it
    gives ("b", or "other": none of them); none when the read says it gives no answer and
    only names an option ("can you explain why 18 is wrong" was graded and the next lesson
    followed, review 2026-11-14). An option's own words beat its letter (``option_said``)."""
    if read.answers is not True:
        return []
    message = ctx.user_message_content or ""
    cards = last_reply_cards(_answered_window(ctx))
    return [
        (card, pick if (said := card.option_said(message)) is None else option_letter(said).lower())
        for card, pick in zip(cards, read.card_picks or [], strict=False)
        if pick != NO_ANSWER
    ]


def _replies_to_the_card(ctx: StreamContext, read: TurnDecision) -> bool:
    """A reply to the last reply's card that the read says gives no answer to it: talked
    through, never laid out as a calculation of its own. "is it 35 or 52?" came back Given to
    Answer on every try once its lesson's note said to do what it asks (review, 2026-11-14);
    a new problem asked after the card stands alone, and keeps its layout."""
    return (
        read.answers is False
        and read.follow in ("answer", "pick")
        and bool(last_reply_cards(_answered_window(ctx)))
    )


def _verdict(card: PracticeCard, pick: str) -> str | None:
    """The server's grade of one answer, in words the reply may repeat as they stand ("Their
    answer '35' isn't one of the options" was, review 2026-11-14), or None for a card with no
    right option named. An option goes by its words: the phone shows no letters. Each line
    says whose answer it grades: "Question 1: 6, right." was read as Question 1 wrong."""
    if card.right is None or card.answer is None:
        return None
    name = card.label or card.question[:60]
    right = card.right[:_OPTION_CHARS]
    index = ord(pick[:1] or "?") - ord("a")
    if pick == OTHER_ANSWER or not 0 <= index < len(card.options):
        return f"{name}: the answer given is none of the options; the right answer is {right}."
    chosen = card.options[index][:_OPTION_CHARS]
    if index == card.answer:
        return f"{name}: the answer given, {chosen}, is right."
    return f"{name}: the answer given, {chosen}, is wrong; the right answer is {right}."


def _grades_the_card(
    ctx: StreamContext, answered: list[tuple[PracticeCard, str]], *, unplaced: bool
) -> bool:
    """A message that answers the last reply's practice cards, in the read's words: the server
    grades each against its card, and the reply opens with that verdict, never a calculation
    laid out of its own; one answer that may be any card's is asked about first. A new
    question asked after a card answers none, and is worked as any question is."""
    if not answered or _worked(ctx) or ctx.instant_reply:
        return False
    _without_worked_layout(ctx)
    if unplaced:
        note_prompt_rule("read.quiz_which")
        ctx.prompt_messages = inject_before_last_user(ctx.prompt_messages, QUIZ_WHICH_NOTE)
        return True
    verdicts = [found for card, pick in answered if (found := _verdict(card, pick))]
    if verdicts:
        note_prompt_rule("read.quiz_answer")
        note = quiz_verdict_note(verdicts)
        ctx.prompt_messages = inject_before_last_user(ctx.prompt_messages, note)
    return True


def _without_worked_layout(ctx: StreamContext) -> None:
    """No ```worked contract: the read says the message asks for no result worked out. With
    one, "Translate the algebraic expression 7x in different word phrases" was answered
    under a Given and a Required, "phrases" set as a symbol (phone, 2026-11-13)."""
    if ctx.worked is None:
        return
    ctx.worked = None
    ctx.prompt_messages = without_worked_contract(ctx.prompt_messages)
    note_prompt_rule("read.not_worked")


# The kinds that reply to the last reply's question or offer, which their note names.
_ANSWERS_THE_REPLY = frozenset({"accept", "decline", "pick", "answer"})


def _follow_note(ctx: StreamContext, read: TurnDecision) -> None:
    """The read's word on how the message leans on the conversation, beside it, in every
    subject: "and b?" was read as a change in physics and told nothing (2026-11-18). A
    lesson, an outline awaiting a pick and the turn after a clarify card read the reply their
    own way (``message_notes``); numbers a server path worked are the reply's to present, and
    a calculation the subject readers gave the ```worked contract is laid out by it."""
    note = FOLLOW_NOTES.get(read.follow or "")
    if note is None or ctx.after_card:
        return
    if _worked(ctx) or ctx.worked is not None:
        return
    if active_lesson_step(ctx.recent_messages) or outline_awaits_pick(ctx.recent_messages):
        return
    note_prompt_rule(f"read.follow_{read.follow}")
    messages = ctx.prompt_messages
    # "To eat", a guess at "Why do cats purr?", got Oakland restaurants "since your favorite
    # color is green" on 2 of 3 (2026-11-15), a word rule having read food in it. Named the
    # question it answers, it was the cat guess on 5 of 5, the recommendation hint kept for
    # an answer that does ask for one ("Italian" to "What cuisine?").
    if read.follow in _ANSWERS_THE_REPLY and (question := _answered_question(ctx, messages)):
        note = f'{note} The question it answers: "{question}"'
    if read.follow != "accept":
        # The word rules' yes ("Carry out that offer now") is the read's to say: "pls" after
        # a reply that offered nothing asks for more, and the rule had it redo the last one.
        messages = without_confirmation_hints(messages)
    ctx.prompt_messages = inject_before_last_user(messages, note)


def _answered_question(ctx: StreamContext, messages: list[dict[str, Any]]) -> str | None:
    """The question the last reply asked, unless a pick note names another: "Is it A or B?"
    after the reply that graded it is about the lettered question before, whose note says so,
    and the last reply's "Want another round?" would point the other way."""
    last = next(
        (
            getattr(m, "content", "")
            for m in reversed(ctx.recent_messages or [])
            if getattr(m, "role", None) == "assistant"
        ),
        "",
    )
    question = _asked_question(last) if isinstance(last, str) else None
    picks = [str(m.get("content")) for m in messages if OPTION_PICK_MARK in str(m.get("content"))]
    return question if question and all(question in pick for pick in picks) else None
