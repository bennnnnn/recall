"""The turn's read by Perplexity's Decider: closed questions, answered with probabilities.

The Qwen read (``turn_decision``) writes its answers as JSON text: about 1.1 s, with p95
1.7 s, and upstream rate limits refused 7-40% of its calls on 2026-11-10. The Decider
answers the same questions as probabilities in 0.33 s (p95 0.71 s), and on the held-out half
of the check-up, think and search corpora (2026-11-10) it read the subject on 99%,
the picture on 99%, the follow-up on 95%, the effort on 94%; the think corpus at 100% recall
with no false thinking; and search at 100% recall, 2.4% false. It writes no text, so a search
query still comes from the text read. Each yes threshold below was picked on the tuning
half; nothing here raises.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any

from app.core.aio import gather_or_cancel
from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.modules.chat.quiz_cards import PracticeCard, option_letter
from app.services.solving import SubjectName

logger = logging.getLogger(__name__)

# Yes thresholds, picked on the tuning half.
_THINK_AT = 0.65
# Everyday and code: a hard question, the strong lane's (the owner's call, 2026-11-10).
_HARD_AT = 0.95
# Maths, physics and chemistry think only when hard: at 0.7 the held-out STEM word problems
# of the think corpus thought on 94% and the check-up's textbook problems agreed
# with their labels on 93%.
_STEM_HARD_AT = 0.7
_LIVE_AT = 0.35
# Below the line but close to it: a reply that then says it can't check live facts is asked
# again and made to search (``tool_loop.live_denial``); further off, it is only offered the
# search. "Top 5 universities in Ethiopia" alone read 0.15 before rankings were named; the
# settled reads this close are mostly about the user's own place ("is it far?", 0.26).
NEAR_LIVE_AT = 0.15
_ASKED_AT = 0.5
# A result to work out (``WORK_QUESTION``, its own call): on the work-need corpus's tuning
# half every threshold from 0.3 to 0.7 laid out every calculation and nothing else, and 0.5 is
# that range's middle; held out (69 turns, Spanish, French and Amharic, "explain how to find",
# follow-ups, a lesson's pick and a quiz answer among them) it laid out 35 of 35 calculations
# and none of the 34 other questions, where a number and a subject laid out 77% of them
# (``tests/behavior/work_need_eval.py``).
_WORK_AT = 0.5
# Going on to the next lesson: the yes of a plain yes or no.
_GOES_ON_AT = 0.5
# Going on with a reply cut off before its end: the yes of a plain yes or no.
_RESUMES_AT = 0.5
# How long the turn's read waits for the work question's call once its own is in: both
# start together and answer in about 0.33 s. The cards' call is waited for as long as the
# read's own budget allows (and the reply waits no longer than ``live_read_wait_seconds``
# for the read): on a card's turn its answers are what the read is for, and dropped 0.6 s
# past the read, a call a second late left "b" ungraded (review, 2026-11-14).
_WORK_GRACE_SECONDS = 0.25
# The read's name for each registered subject (``SubjectName``; its choices call maths
# "maths"). The read's own words for them are the subject question's criteria below, part
# of its measured prompt; ``tests/services/test_subject_completeness.py`` holds the two and
# Auto's lanes for them (``routing_lanes.ROUTING.decided``) to the registry.
READ_SUBJECTS: Mapping[str, SubjectName] = MappingProxyType(
    {"maths": "math", "physics": "physics", "chemistry": "chemistry"}
)
_STEM = frozenset(READ_SUBJECTS)

# How the live question reads a short follow-up: as the question it stands for (below).
LIVE_IN_CONTEXT = (
    "Judge what the last message asks once the conversation fills in what it leaves out "
    "(a yes to the assistant's question asks what that question offered)."
)

QUESTIONS: dict[str, dict[str, Any]] = {
    "subject": {
        "type": "choice",
        "instructions": (
            "What is the user's last message about? A follow-up takes the subject of what "
            'it follows ("draw it" after a circuit is physics).'
        ),
        "criteria": {
            "everyday": "anything else: advice, plans, writing, facts, other subjects such as "
            "biology or history, small talk, even when a word sounds like a subject",
            "maths": "maths: a problem to work out, a concept, a practice question",
            "physics": "physics, gas laws and heat included: a problem, a concept, a practice "
            "question",
            "chemistry": "chemistry: a problem, a concept, a practice question, a molecule",
            "money": "the user's own money worked out with amounts: a loan, mortgage or card "
            "payment, savings or investment growth",
            "code": "writing, explaining or fixing code, or using a programming tool",
        },
    },
    "think": {
        "type": "noul",
        "instructions": (
            "Must a careful answer be reasoned out before it is written: several dependent "
            "steps or parts, a word problem to set up, a proof, a comparison or design "
            "trade-off to weigh, code to write or debug, a tricky logic puzzle? Not for chat, "
            "simple facts, how-to steps, writing a message, a one-step calculation, a "
            "textbook problem one formula answers, or a single equation to solve."
        ),
    },
    "hard": {
        "type": "noul",
        "instructions": (
            "Is the reasoning the work itself: a word problem to set up with unknowns or "
            "rates, a proof, a problem in several parts, a logic puzzle, a decision with many "
            "factors and numbers, a system or algorithm to design, hard debugging? Not for a "
            "textbook problem a formula or two answer, a short comparison or plan, or short "
            "code."
        ),
    },
    "picture": {
        "type": "choice",
        "instructions": (
            "What does the last message ask to see? Only when it asks to draw, sketch, plot, "
            'graph, chart, show, a picture, or what something looks like; "draw it" shows '
            "what the conversation is about."
        ),
        "criteria": {
            "none": "it asks to see nothing, even a problem a figure would help; a map",
            "graph": "a curve, or a chart of data",
            "diagram": "a circuit, forces, rays, a wave or a moving scene, a geometric figure, "
            "a flowchart or mind map",
            "molecule": "a molecule's structure, flat or 3D",
            "photo": "a photo of a real thing, place, animal or person",
            "image": "an imagined picture to paint: a scene, an animal doing something, a "
            "logo, a poster",
        },
    },
    "follow": {
        "type": "choice",
        "instructions": (
            "What does the last message do with the assistant's last reply? People text "
            "short, so read it against that reply's end, where its question or offer is."
        ),
        "criteria": {
            "none": "it stands alone: a new question or request, or there are no earlier turns",
            "solve": "work out a problem an earlier message stated or the assistant posed "
            "(do it, solve it, what's the answer)",
            "explain": "asks what the last answer meant or why (why?, how?, wdym, huh, "
            "simpler, step by step)",
            "more": "asks for more of the last answer or to keep going (more, go on, and?, "
            "what else, pls when nothing was offered)",
            "change": "the earlier problem or work changed or asked something else (what if, "
            "the second derivative, make it shorter, in a table, another one)",
            "draw": "show what the conversation is about (draw it, graph it)",
            "accept": "yes to something the last reply offered or proposed to do (yes, yap, "
            "sure, go, pls, do it)",
            "decline": "no to the last reply's offer or question, or a no thanks with "
            "nothing offered (nah, no thanks, nah im good, not now)",
            "pick": "chooses one of the options or items the last reply listed or asked "
            "between (the 2nd, pasta, both, b)",
            "answer": "gives a value or detail the last reply asked for (a number, a name, a "
            "place, how many), a quiz answer, or their own answer to check",
            "react": "a reaction, not a request, to a reply that asked and offered nothing "
            "(ok, cool, lol, thanks, wow, makes sense)",
        },
    },
    # "Top 5 in Ethiopia" after a search for the world's top universities read 0.14, its "Yes"
    # to "Do you mean the universities?" 0.06 and "Top 5 universities in Ethiopia" alone 0.15
    # (Pro phone test, 2026-11-11): rankings were not among the facts that change, and a
    # reply to the assistant's question was judged as its own words. Naming both, the 30
    # follow-ups of ``search_need_corpus.json`` read in context ("follow-up in context": the
    # same words live after one question, settled after another) went from 10 of 15 live
    # searched to 15 of 15, none of the 15 settled; the rest stayed at 63 of 63 live searched
    # and 1 of 90 settled.
    "live": {
        "type": "noul",
        "instructions": (
            "Does the answer need facts that change, or that a model trained in the past "
            "cannot know as of today: news, results, rankings, the latest of anything, who "
            "holds an office now, prices, weather, schedules, opening hours, places near the "
            f"user? {LIVE_IN_CONTEXT} "
            "Not advice, how-to, settled knowledge, maths, writing, the user's own life or "
            "chats, getting to a place already named, or work on the conversation itself."
        ),
    },
    "asked": {
        "type": "noul",
        "instructions": (
            "Does the last message ask to search the web or look something up online "
            "(google it, check online)? A search of the user's own chats or notes is not."
        ),
    },
}

# Whether the reply works a result out, and so is laid out as working (Given, Required, the
# steps, the Answer: ``chat.worked_turn``). A digit alone said yes: "Translate the algebraic
# expression 7x in different word phrases" got a Given and a Required, with "phrases" set as
# a symbol (phone, 2026-11-13). Asked in a call of its own, beside the turn's: the Decider
# weighs a call's questions together, and asked among them it moved the measured ``think``
# (two thinking questions of the think corpus read as plain, 96% recall to 92%).
WORK_QUESTION: dict[str, dict[str, Any]] = {
    "work": {
        "type": "noul",
        "instructions": (
            "Does the last message ask for a result to be worked out: a value to calculate, "
            "an equation or inequality to solve, an expression to simplify, expand, factorise "
            "or differentiate, a unit to convert, an equation to balance, a quantity a "
            "problem asks for, or the same work again with a value changed? Not for what a "
            "symbol, number or term means, an expression said in words or words written as "
            "an expression, a definition, a law or formula stated, a concept or reason "
            "explained, naming or classifying, a fact to recall, examples, or practice "
            "questions to set."
        ),
    },
}


# A practice card the message may answer, at most this many from the last reply (a set of
# five), each its own choice question; the most options one names by letter; and how much of
# a card's question, code and each option the questions quote (a card is the model's text).
CARDS_READ = 5
_OPTIONS_READ = 8
_QUESTION_CHARS = 300
_CODE_CHARS = 300
_OPTION_CHARS = 120
# The answer a choice question gives when the message names no option of its card, and the
# one when it answers with something that is none of them.
NO_ANSWER = "none"
OTHER_ANSWER = "other"
# Whether the message gives its answer at all: "can you explain why 18 is wrong" names an
# option as plainly as "18" does, and was graded as the answer, the next lesson after it
# (review, 2026-11-14). And, after several cards, whether its one answer says which it is
# for: a lone "B" was graded against each of three.
_ANSWERS_AT = 0.5
_UNPLACED_AT = 0.5


def lesson_questions(cards: Sequence[PracticeCard], *, lesson: bool) -> dict[str, dict[str, Any]]:
    """The questions about a message after practice cards or a lesson, asked in a call of their
    own: which option of each card it names, whether it gives that as its answer, and whether
    it asks to go on.

    In the owner's study chat (2026-11-14) "b" for the card's B was graded wrong, "a" right and
    "the second one" as its third option: the reply's model was told only the right answer's
    words. A model reads which option the message names, in any words; the server grades it."""
    questions: dict[str, dict[str, Any]] = {}
    read = cards[:CARDS_READ]
    for number, card in enumerate(read, start=1):
        criteria = {
            option_letter(index).lower(): f"{option_letter(index)}: {option[:_OPTION_CHARS]}"
            for index, option in enumerate(card.options[:_OPTIONS_READ])
        }
        criteria[OTHER_ANSWER] = "an answer to it that is none of these options"
        criteria[NO_ANSWER] = (
            "no answer to it: it asks to go on or for more, asks something else, answers yes "
            "or no to an offer, or picks one of the choices a question after the card offered "
            "(the second one, after: a harder one, or move on?)"
        )
        code = f" (code: {card.code[:_CODE_CHARS]})" if card.code else ""
        questions[f"card{number}"] = {
            "type": "choice",
            "instructions": (
                f"The assistant's last reply set the practice question "
                f"{card.question[:_QUESTION_CHARS]!r}{code}. Which option does the user's last "
                "message name as its answer to it: by its letter (B), its place (the second "
                "one, option 2), its words, or a value equal to it?"
            ),
            "criteria": criteria,
        }
    if read:
        questions["answers"] = {
            "type": "noul",
            "instructions": (
                "The assistant's last reply set practice questions. Does the user's last "
                "message give its own answer to one of them: a letter, a place, an option's "
                "words or a value, a guess included (is it 17?, I think 18)? Not a question "
                "that names an option to ask something else about it or the topic (why is 18 "
                "wrong?, what does 52 mean?, does 17 hold for sodium too?), a question between "
                "two answers (is it 35 or 52?), asking for the answer or a hint, an answer to "
                "an earlier question the last reply did not set, a yes or no to an offer, or "
                "asking to go on."
            ),
        }
    if len(read) > 1:
        questions["unplaced"] = {
            "type": "noul",
            "instructions": (
                f"The assistant's last reply set {len(read)} practice questions. Does the "
                "user's last message give one answer without saying which of them it is for "
                "(a lone B)? Not answers to several of them in turn (1. b 2. c, or b, c, a), "
                "nor one it says is for a question (for number 2, the neutron)."
            ),
        }
    if lesson:
        questions["goes_on"] = {
            "type": "noul",
            "instructions": (
                "The assistant's last reply taught a lesson. Does the user's last message ask to "
                "go on to the next lesson (next, ok, continue, got it, or an answer to its "
                "practice question)? Not a question, one between two answers included (is it "
                "35 or 52?), a yes to another offer the reply made, a pick among other choices "
                "it offered, or another request."
            ),
        }
    return questions


# Asked when the last reply was cut off before its end (``model_routing.thinking``): going
# on writes the rest with no thinking pass, and anything else is a turn of its own.
RESUME_QUESTION: Mapping[str, dict[str, Any]] = MappingProxyType(
    {
        "resumes": {
            "type": "noul",
            "instructions": (
                "The assistant's last reply was cut off before it finished. Does the user's "
                "last message ask it to go on with that reply, in any words or language "
                "(continue, go on, keep going, finish it, and the rest?)? Not a new question "
                "or request, a question about what the reply said, or a correction of it."
            ),
        }
    }
)


def _picks(answers: dict[str, Any]) -> list[str] | None:
    """Each card's chosen option ("a", "other", "none"), in order; None when not asked."""
    picks = [
        str(get_choice(answers, f"card{number}") or NO_ANSWER)
        for number in range(1, CARDS_READ + 1)
        if f"card{number}" in answers
    ]
    return picks or None


def _yes(odds: float | None, at: float) -> bool | None:
    """A yes or no question's answer at its threshold; None when it was not asked."""
    return None if odds is None else odds >= at


def get_choice(answers: dict[str, Any], name: str) -> Any:
    answer = answers.get(name)
    if answer is None:
        return None
    return answer.get("choice") if isinstance(answer, dict) else getattr(answer, "choice", None)


def decision_fields(answers: dict[str, Any], *, has_earlier: bool) -> dict[str, Any] | None:
    """The read's fields from the Decider's answers (``DeciderAnswer`` objects or dicts);
    None when a question went unanswered."""

    def get(name: str, key: str) -> Any:
        answer = answers.get(name)
        if answer is None:
            return None
        return answer.get(key) if isinstance(answer, dict) else getattr(answer, key, None)

    subject = get("subject", "choice")
    think, hard = get("think", "noul"), get("hard", "noul")
    live, asked = get("live", "noul"), get("asked", "noul")
    if subject is None or None in (think, hard, live, asked):
        return None
    work = get("work", "noul")
    if subject in _STEM:
        # Only the hard ones think; ``model_routing.decided`` gives "high" the model's
        # level that thinks.
        effort = "high" if hard >= _STEM_HARD_AT else "none"
    else:
        effort = (
            "high"
            if think >= _THINK_AT and hard >= _HARD_AT
            else ("low" if think >= _THINK_AT else "none")
        )
    return {
        "subject": subject,
        "think": effort != "none",
        "hard": effort == "high",
        "picture": get("picture", "choice"),
        "follow": get("follow", "choice") if has_earlier else "none",
        "live": max(live, asked) >= _LIVE_AT,
        "live_odds": max(live, asked),
        "asked": asked >= _ASKED_AT,
        # None (unanswered): the rules decide the layout.
        "work": None if work is None else work >= _WORK_AT,
        "card_picks": _picks(answers),
        "answers": _yes(get("answers", "noul"), _ANSWERS_AT),
        "unplaced": _yes(get("unplaced", "noul"), _UNPLACED_AT),
        "goes_on": _yes(get("goes_on", "noul"), _GOES_ON_AT),
        "resumes": _yes(get("resumes", "noul"), _RESUMES_AT),
    }


async def decide_turn(
    settings: Settings,
    state: str,
    *,
    has_earlier: bool,
    seconds: float,
    ask_work: bool = False,
    lesson: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """The Decider's read of ``state`` (the message, its earlier turns quoted), or None. With
    ``ask_work`` the work question, and with ``lesson`` the questions about the last reply's
    cards (``lesson_questions``), go in calls of their own begun beside it: the Decider weighs
    one call's questions together. Each ends when the read does, whatever ends it (an answer,
    a failure, the reply's wait, a Stop)."""
    from app.gateways.decider_gateway import decide
    from app.gateways.llm_spend import meter_reported_cost

    alias = ROUTING.decider
    beside: list[tuple[asyncio.Task[Any], float | None]] = []
    started = time.monotonic()
    try:
        from app.models import model_catalog

        model = model_catalog.get(alias).model.removeprefix("openrouter/")
        calls: tuple[tuple[dict[str, dict[str, Any]] | None, float | None], ...] = (
            (WORK_QUESTION if ask_work else None, _WORK_GRACE_SECONDS),
            (lesson or None, None),
        )
        for questions, grace in calls:
            if questions is not None:
                read = asyncio.create_task(
                    decide(settings, model=model, state=state, questions=questions, seconds=seconds)
                )
                read.add_done_callback(_metered_work(alias))
                beside.append((read, grace))
        try:
            reply = await decide(
                settings, model=model, state=state, questions=QUESTIONS, seconds=seconds
            )
        except Exception as exc:
            _note_health(settings, alias, started, exc)
            raise
        _note_health(settings, alias, started, None)
        meter_reported_cost(alias, reply.usage.cost)
        answers = dict(reply.answers)
        # The cards' call (no grace of its own) is waited for to the read's whole budget.
        left = max(0.0, seconds - (time.monotonic() - started))
        waits = [(read, left if grace is None else grace) for read, grace in beside]
        for found in await gather_or_cancel(*(_work_answers(*call) for call in waits)):
            answers.update(found)
    except Exception as exc:  # A read is a hint: the text read or the rules decide.
        logger.info("decider read failed (%s)", type(exc).__name__)
        return None
    finally:
        for read, _grace in beside:
            if not read.done():
                read.cancel()
    return decision_fields(answers, has_earlier=has_earlier)


def _note_health(
    settings: Settings, alias: str, started: float, failure: BaseException | None
) -> None:
    """The Decider's call as one sample on its breaker (``services.model_health``), so a
    Decider outage opens it and turns stop waiting the read's whole timeout for it
    (MODEL-07). Written beside the turn, never in its way; a cancelled call (the reply
    stopped waiting) says nothing about the provider and leaves none."""
    from app.core.background_tasks import create_background_task
    from app.core.redis import get_redis_client
    from app.services.model_health import HealthSample, record_samples

    if not settings.openrouter_api_key:
        return  # No key, no call went out: nothing about the provider to note.
    sample = HealthSample(
        alias,
        latency_ms=(time.monotonic() - started) * 1000,
        success=failure is None,
        cause=_failure_cause(failure),
    )
    try:
        create_background_task(record_samples(get_redis_client(), [sample]))
    except Exception as exc:  # A health sample is best-effort: the read goes on without it.
        logger.info("decider health sample not written (%s)", type(exc).__name__)


def _failure_cause(failure: BaseException | None) -> str | None:
    """``rate_limit`` for a refusal for capacity, which opens the breaker by itself."""
    response = getattr(failure, "response", None)
    return "rate_limit" if getattr(response, "status_code", None) == 429 else None


async def _work_answers(work_read: asyncio.Task[Any], grace: float) -> dict[str, Any]:
    """A call's answers beside the turn's read (the work question, the cards'), waited for
    ``grace`` past it; none (the rules decide) when it is late or failed."""
    try:
        reply = await asyncio.wait_for(work_read, grace)
    except TimeoutError:  # Late: the rules lay the turn out.
        return {}
    except Exception as exc:  # Failed: the rules lay the turn out.
        logger.info("decider work read failed (%s)", type(exc).__name__)
        return {}
    return dict(reply.answers)


def _metered_work(alias: str) -> Callable[[asyncio.Task[Any]], None]:
    """Each finished call beside the read metered against the day's spend, and a failed one's
    error read (asyncio logs an unread one as an error); a failure the turn awaited is logged
    there."""
    from app.gateways.llm_spend import meter_reported_cost

    def settle(task: asyncio.Task[Any]) -> None:
        if task.cancelled():
            return
        if task.exception() is None:
            meter_reported_cost(alias, task.result().usage.cost)

    return settle
