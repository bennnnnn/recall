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

import logging
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from app.core.config import Settings
from app.models.routing_lanes import ROUTING
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
# A result to work out (``work``): on the work-need corpus's tuning half every threshold from
# 0.3 to 0.6 laid out every calculation and nothing else; at 0.5 the held-out half laid out
# 18 of 18 calculations and 1 of 18 other questions ("1 newton in base SI units", 0.54),
# where a number and a subject laid out 77% of them (``tests/behavior/work_need_eval.py``).
_WORK_AT = 0.5
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
        "instructions": "How does the last message relate to the earlier turns?",
        "criteria": {
            "none": "it stands alone: a new question or request, or there are no earlier turns",
            "solve": "work out a problem an earlier message stated or the assistant posed "
            "(do it, solve it, what's the answer)",
            "explain": "more on the last answer (step by step, why?, explain it simply)",
            "change": "the earlier problem or work changed or asked something else (what if, "
            "the second derivative, make it shorter, in a table, another one)",
            "draw": "show what the conversation is about (draw it, graph it)",
            "answer": "a reply to the assistant's question or offer: a value it asked for, a "
            "choice, yes or no, accepting an offer, a quiz answer",
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
    # Whether the reply works a result out, and so is laid out as working (Given, Required,
    # the steps, the Answer: ``chat.worked_turn``). A digit alone said yes: "Translate the
    # algebraic expression 7x in different word phrases" got a Given and a Required, with
    # "phrases" set as a symbol (phone, 2026-11-13).
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
    "asked": {
        "type": "noul",
        "instructions": (
            "Does the last message ask to search the web or look something up online "
            "(google it, check online)? A search of the user's own chats or notes is not."
        ),
    },
}


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
    }


async def decide_turn(
    settings: Settings, state: str, *, has_earlier: bool, seconds: float
) -> dict[str, Any] | None:
    """The Decider's read of ``state`` (the message, its earlier turns quoted), or None."""
    from app.gateways.decider_gateway import decide
    from app.gateways.llm_spend import meter_reported_cost
    from app.models import model_catalog

    alias = ROUTING.decider
    try:
        reply = await decide(
            settings,
            model=model_catalog.get(alias).model.removeprefix("openrouter/"),
            state=state,
            questions=QUESTIONS,
            seconds=seconds,
        )
    except Exception as exc:  # A read is a hint: the text read or the rules decide.
        logger.info("decider read failed (%s)", type(exc).__name__)
        return None
    meter_reported_cost(alias, reply.usage.cost)
    return decision_fields(reply.answers, has_earlier=has_earlier)
