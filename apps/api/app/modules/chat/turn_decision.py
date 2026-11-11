"""How Auto handles a message: one fast model call reads it, not word rules.

The read began as the search decider (does the answer depend on facts that change?). A
100-chat check-up on Pro (2026-11-10) found the rest of the turn's handling decided by word
rules: 76 of 134 turns were written by the everyday model, easy STEM questions the subject
readers missed thought for up to 28 s, hard questions almost never reached the strong
model, and "draw the circuit" painted an AI picture. So the same call, beside the turn's
prep, now also answers what the message is about (``subject``), how much it must be reasoned
out (``effort``), what picture it asks to see (``picture``) and how it relates to the turn
before (``follow``). The server maps that to a lane and a thinking level through catalog
data (``model_routing.decided``); the word rules decide only when the read gives no answer
in time.

Search: yes (the answer is live, or the user asked), and the read's own query is searched
before the reply's call, which then answers from the results in one call. No, and the
reply's call carries no search tool: the read is the one decider
(``chat.tool_loop.reply_calls``). No answer in time, and the reply's model holds the tool.

In one chat about a hot MacBook Air (2026-11-09) the read saw only the reply before the
message, sent to it as a chat turn: it answered "Can i just buy another one" by searching
"iPhone 16 price". It now sees the last two exchanges, quoted in one message, so it judges
the message instead of carrying on the chat. ``tests/behavior/search_need_eval.py``,
``think_need_eval.py`` and ``decider_eval.py`` measure it on their labelled sets. Nothing
here raises into a turn.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import Settings
from app.models.routing_lanes import ROUTING

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 1200
# Each earlier message the read sees, and how many: the last two exchanges.
_EARLIER_CHARS = 400
_EARLIER_MESSAGES = 4
# Seven short keys: about 45 tokens of JSON.
_MAX_TOKENS = 120

Subject = Literal["everyday", "maths", "physics", "chemistry", "money", "code"]
Effort = Literal["none", "low", "high"]
Picture = Literal["none", "graph", "diagram", "molecule", "photo", "image"]
Follow = Literal["none", "solve", "explain", "change", "draw", "answer"]

_SYSTEM = (
    "Today is {today}. Read the user's last message and say how an assistant app should "
    "handle it.\n\n"
    "live is true only when the answer needs facts that change, or that a model trained in "
    "the past cannot know as of today:\n"
    "- news and events, results and scores, the latest or the next of anything, whether "
    "something is out yet\n"
    "- who holds an office or a title now\n"
    "- prices, costs and rates; weather; schedules and opening hours\n"
    "- a person or a product in the news\n"
    "- places to find near the user (the nearest shop, a restaurant, what is open)\n\n"
    "live is false for everything else, even when the conversation before it was about "
    "something live:\n"
    "- greetings, small talk and thanks; the user's own life, plans and feelings\n"
    "- advice and choices: whether to repair, replace or buy something, what to do, which "
    "to pick\n"
    "- how things work and how to do something: steps, settings and checks on a phone, "
    "computer or app (unless it names a model or version that may be newer than you "
    "know); who makes or repairs something\n"
    "- maths, science, writing, code, history and other settled knowledge\n"
    "- where the user is: the app knows their place\n"
    "- what the user told you or keeps here: their earlier chats, memory, notes, to-dos "
    "and files, even when they ask you to search or look them up\n"
    "- getting from the user to a place the conversation already named, on foot, by car, "
    "bike, bus or train (can they walk, how to get there, how long, how far): the reply "
    "answers with a map link, which shows the route, its time and the next bus or train; "
    "never a web search\n"
    "- work on the conversation itself: a summary of it, another practice problem, "
    "explaining something again, a shorter version\n\n"
    "Earlier turns, when given, show what the last message refers to; decide for the last "
    "message.\n\n"
    "subject is what the message is about, a follow-up taking the subject of what it "
    'follows ("draw it" after a circuit is physics):\n'
    "- maths, physics or chemistry: that school subject: a problem to work out, a concept, "
    "a practice question, a molecule to draw; gas laws and heat are physics\n"
    "- money: the user's own money worked out with amounts: a loan, mortgage or card "
    "payment, savings or investment growth\n"
    "- code: writing, explaining or fixing code, or using a programming tool\n"
    "- everyday: anything else (advice, plans, writing, facts, other subjects such as "
    'biology or history, small talk), even when a word sounds like a subject ("our '
    'chemistry is off", "draw up a budget")\n\n'
    "think is true when a careful answer must be reasoned out before it is written: "
    "several dependent steps or parts, a word problem to set up, a proof, a comparison or "
    "design trade-off to weigh, code to write or debug (why it misbehaves counts), a "
    "tricky logic puzzle, and a follow-up asking for more of such work (the next parts of "
    "a problem in the chat). think is false for chat, simple facts, a concept or a "
    "difference explained, how-to steps, advice, a list or plan from common knowledge (what "
    "to pack, a workout, a recipe), writing or rewording a message, a one-step "
    "calculation, a textbook problem one formula "
    "answers, the same problem again with a value changed, a request to draw or show "
    "something, setting a practice question, and a single equation or expression to "
    "solve, differentiate or simplify (the app's solver checks those).\n"
    "hard is true when that reasoning is long or deep: a proof of more than a few lines, "
    "many steps or parts, a decision with many factors and numbers, a system or algorithm "
    "to design, hard debugging, a puzzle that needs case analysis; false otherwise.\n\n"
    "picture is what the message asks to see: it says draw, sketch, plot, graph, chart, "
    "show me, a picture of, or what something looks like. Otherwise none, even for a "
    "problem a figure would help. graph: a curve, or a chart of data; diagram: a "
    "circuit, forces, rays, a wave or a moving scene, a geometric figure, a flowchart or "
    "mind map; molecule: a molecule's structure, flat or 3D; photo: a real thing, place, "
    "animal or person; image: an imagined picture to paint (a scene, an animal doing "
    'something, a logo, a poster). A map is none. "Draw it" shows what the conversation '
    "is about: a circuit is a diagram, a compound a molecule, a curve a graph.\n\n"
    "follow is how the message relates to the earlier turns; with no earlier turns it is "
    "none:\n"
    "- none: it stands alone, a new question or request\n"
    "- solve: work out a problem an earlier message stated, also one the assistant posed "
    '("do it", "solve it", "what\'s the answer")\n'
    '- explain: more on the last answer ("step by step", "why?", "explain it simply")\n'
    "- change: the earlier problem or work with something changed or something else asked "
    'of it ("what if it was 30 m/s?", "now the second derivative", "and the slowest?", '
    '"make it shorter", "in a table", "another one")\n'
    '- draw: show what the conversation is about ("draw it", "graph it", "show me it '
    'moving")\n'
    "- answer: a reply to the assistant's question or offer: a value or detail it asked "
    'for, a choice, yes or no, accepting an offer ("do it" after "want me to make a '
    "plan?\"), a quiz answer, or the user's own answer to check\n\n"
    "Reply with JSON only, eight keys in this order: asked is true when the user's last "
    "message asks you to search the web or look up something about the world (a fact, a "
    "person, a place, a thing), google it or check online, whatever the topic; a search of "
    "their own chats, memory, notes, to-dos or files is not asked (the app holds those), "
    "and otherwise asked is false; query is what a person would type into a search engine to "
    "answer the message, standing alone (spell out who or what the conversation is about: "
    "a full name, a product's model, a place), in the message's language, with no month or "
    'year unless the message names one, or "" when live and asked are both false; live; '
    'subject; think; hard; picture; follow. Example: {{"asked": false, "query": "", '
    '"live": false, "subject": "physics", "think": false, "hard": false, "picture": '
    '"diagram", "follow": "draw"}}.'
)


def _known(value: Any, choices: tuple[str, ...]) -> str | None:
    """A choice the schema names, else None: one odd field leaves the rest of the read."""
    text = str(value).strip().lower() if value is not None else ""
    return text if text in choices else None


class TurnDecision(BaseModel):
    # The user asked for a search of the web ("google it", "can you look up …"). Told only
    # that such a message is live, the read still called "who invented the telephone"
    # settled. A search of their own chats or memory is not one: its words would go to the
    # web, and ``recall_chats`` is what they meant.
    asked: bool = False
    query: str = Field(default="", max_length=200)
    live: bool
    # What the message is about, how hard it is, the picture it asks to see and how it
    # follows the turn before. None: the read gave no usable answer for that field, and the
    # word rules decide it.
    subject: Subject | None = None
    # Whether the answer must be reasoned out first, and whether at length: the effort.
    think: bool | None = None
    hard: bool = False
    effort: Effort | None = None
    picture: Picture | None = None
    follow: Follow | None = None

    @field_validator("subject", mode="before")
    @classmethod
    def _subject(cls, value: Any) -> str | None:
        return _known(value, ("everyday", "maths", "physics", "chemistry", "money", "code"))

    @field_validator("picture", mode="before")
    @classmethod
    def _picture(cls, value: Any) -> str | None:
        return _known(value, ("none", "graph", "diagram", "molecule", "photo", "image"))

    @field_validator("follow", mode="before")
    @classmethod
    def _follow(cls, value: Any) -> str | None:
        return _known(value, ("none", "solve", "explain", "change", "draw", "answer"))

    @property
    def searches(self) -> bool:
        """The turn searches before the reply: its answer is live, or the user asked."""
        return self.live or self.asked

    @model_validator(mode="after")
    def _effort(self) -> TurnDecision:
        """none, low or high, from whether the answer must be reasoned out and how deeply.
        Two yes-or-no answers held the measured ``think`` wording (2026-11-09): asked for a
        three-way effort, the read called a four-part word problem "none"."""
        if self.think is not None:
            self.effort = "high" if self.think and self.hard else "low" if self.think else "none"
        return self


def earlier_turns(recent: list[Any] | None) -> list[tuple[str, str]]:
    """The last exchanges of an oldest-first window, as the read sees them: what a short
    follow-up ("How much", "Can I walk?", "Draw it") refers to."""
    turns = [
        (role, content[:_EARLIER_CHARS])
        for message in recent or []
        if (role := getattr(message, "role", None)) in {"user", "assistant"}
        and isinstance(content := getattr(message, "content", None), str)
        and content.strip()
    ]
    return turns[-_EARLIER_MESSAGES:]


def decision_messages(text: str, earlier: list[tuple[str, str]]) -> list[dict[str, str]]:
    """The instructions, and one message to judge. The earlier turns are quoted in it, not
    sent as turns: given them as the chat, a model answered the user instead of judging."""
    today = datetime.now(UTC).strftime("%B %Y")
    quoted = "\n".join(
        f"{'User' if role == 'user' else 'Assistant'}: {content}" for role, content in earlier
    )
    last = f"The user's last message: {text[:_MAX_INPUT_CHARS]}"
    return [
        {"role": "system", "content": _SYSTEM.format(today=today)},
        {"role": "user", "content": f"Earlier turns:\n{quoted}\n\n{last}" if quoted else last},
    ]


async def read_decision(
    settings: Settings,
    text: str,
    *,
    earlier: list[tuple[str, str]],
    model_alias: str | None = None,
) -> TurnDecision | None:
    """How to handle the message; None: no read. ``model_alias`` is for measurement."""
    question = text.strip()
    if not question:
        return None
    # Imported here: SymPy pool workers import chat's readers, not the gateway.
    from app.core.redis import get_redis_client
    from app.gateways.structured_completion import complete_structured
    from app.services import quota as quota_service

    try:
        # Past the day's spend cap, or with it unreadable, nothing is read: the word rules
        # and the reply's model decide.
        if await quota_service.global_spend_exceeded(get_redis_client(), settings):
            return None
        read = await complete_structured(
            settings=settings,
            model_alias=model_alias or ROUTING.live_read,
            messages=decision_messages(question, earlier),
            schema=TurnDecision,
            max_tokens=_MAX_TOKENS,
            timeout_seconds=settings.live_read_timeout_seconds,
            allow_fallback=False,
            quiet_timeout=True,
        )
    except Exception as exc:  # A read is a hint: any failure leaves the turn to the rules.
        logger.info("turn decision failed (%s)", type(exc).__name__)
        return None
    if read is not None and not earlier:
        # Nothing came before it: a problem the message states itself ("Solve 3x + 7 = 22")
        # was read as a follow-up asking to solve one.
        read.follow = "none"
    return read


def start_turn_decision(
    settings: Settings, text: str, *, recent: list[Any] | None
) -> asyncio.Task[TurnDecision | None] | None:
    """The read, started now so it runs beside the turn's prep; None when it is off.
    ``recent``: the chat's window before this message, oldest first. Search off still
    reads: the lane and the thinking come from it too."""
    if not settings.live_read_enabled:
        return None
    return asyncio.create_task(read_decision(settings, text, earlier=earlier_turns(recent)))


async def turn_decision_result(
    task: asyncio.Task[TurnDecision | None] | None, settings: Settings
) -> TurnDecision | None:
    """The read, when it answered within ``live_read_wait_seconds`` of the reply asking:
    the reply waits no longer than that for it, whatever the read's own timeout."""
    if task is None:
        return None
    try:
        read = await asyncio.wait_for(task, settings.live_read_wait_seconds)
    except TimeoutError:
        return None
    return read
