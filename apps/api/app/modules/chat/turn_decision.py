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
the message instead of carrying on the chat. ``tests/behavior/search_need_eval.py``
and ``think_need_eval.py`` measure it on their labelled sets. Nothing
here raises into a turn.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.modules.chat.decider_read import NEAR_LIVE_AT, RESUME_QUESTION, lesson_questions
from app.modules.chat.model_routing.thinking import follows_a_cut_off_reply
from app.modules.chat.quiz_cards import (
    block_end_of_cards,
    last_reply_cards,
    option_letter,
    practice_cards,
)
from app.modules.turn_reading.lesson_flow import active_lesson_step

logger = logging.getLogger(__name__)

_MAX_INPUT_CHARS = 1200
# Each earlier message the read sees, and how many: the last two exchanges.
_EARLIER_CHARS = 400
_LAST_REPLY_CHARS = 1500  # "Where is the golf": the course was past 400 (2026-11-15).
# Of those, the last reply's end, where its question or offer is.
_END_CHARS = 400
_EARLIER_MESSAGES = 4
# A reply's practice card the cut leaves out, quoted after it: its question and options, then
# what the reply says after it.
_CARD_CHARS = 300
_CLOSING_CHARS = 200
# Eight short keys: about 55 tokens of JSON.
_MAX_TOKENS = 120
# The backup read is asked only with this much of the budget left: it answers in about 0.7 s
# (p95 0.82 s on the decider corpus).
_BACKUP_MIN_SECONDS = 0.8

Subject = Literal["everyday", "maths", "physics", "chemistry", "money", "code"]
Effort = Literal["none", "low", "high"]
Picture = Literal["none", "graph", "diagram", "molecule", "photo", "image"]
# How the message leans on the last reply. A texted reply is most of a chat ("yap", "nah",
# "the 2nd", "wdym", "lol ok"; owner, 2026-11-21), and one "answer" for all of them told
# the reply to go on with an offer it never made: "nah im good" after the sky's colour got
# "Glad to hear it", and "lol ok" a reply about the words "lol ok". Each kind has its note
# (``FOLLOW_NOTES``); ``tests/behavior/follow_eval.py`` measures the read on them.
Follow = Literal[
    "none",
    "solve",
    "explain",
    "more",
    "change",
    "draw",
    "accept",
    "decline",
    "pick",
    "answer",
    "react",
]
FOLLOWS: tuple[str, ...] = get_args(Follow)

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
    "hard is true when the reasoning is the work itself: a word problem to set up with "
    "unknowns or rates, a proof, a problem in several parts, a logic puzzle, a decision "
    "with many factors and numbers, a system or algorithm to design, hard debugging. hard "
    "is false for a textbook problem a formula or two answer, a short comparison or plan, "
    "and short code.\n\n"
    "picture is what the message asks to see: it says draw, sketch, plot, graph, chart, "
    "show me, a picture of, or what something looks like. Otherwise none, even for a "
    "problem a figure would help. graph: a curve, or a chart of data; diagram: a "
    "circuit, forces, rays, a wave or a moving scene, a geometric figure, a flowchart or "
    "mind map; molecule: a molecule's structure, flat or 3D; photo: a real thing, place, "
    "animal or person; image: an imagined picture to paint (a scene, an animal doing "
    'something, a logo, a poster). A map is none. "Draw it" shows what the conversation '
    "is about: a circuit is a diagram, a compound a molecule, a curve a graph.\n\n"
    "follow is what the message does with the assistant's last reply; people text short "
    '("yap", "nah", "the 2nd", "wdym"), so read it against that reply\'s end, where '
    "its question or offer is; with no earlier turns it is none:\n"
    "- none: it stands alone, a new question or request\n"
    "- solve: work out a problem an earlier message stated, also one the assistant posed "
    '("do it", "solve it", "what\'s the answer")\n'
    '- explain: asks what the last answer meant or why ("why?", "how?", "wdym", "huh", '
    '"simpler", "step by step")\n'
    '- more: asks for more of the last answer or to keep going ("more", "go on", "and?", '
    '"what else", "pls" when nothing was offered)\n'
    "- change: the earlier problem or work with something changed or something else asked "
    'of it ("what if it was 30 m/s?", "now the second derivative", "and the slowest?", '
    '"make it shorter", "in a table", "another one")\n'
    '- draw: show what the conversation is about ("draw it", "graph it", "show me it '
    'moving")\n'
    '- accept: yes to something the last reply offered or proposed to do ("yes", "yap", '
    '"sure", "go", "pls", "do it")\n'
    "- decline: no to the last reply's offer or question, or a no thanks with nothing "
    'offered ("nah", "no thanks", "nah im good", "not now")\n'
    "- pick: chooses one of the options or items the last reply listed or asked between "
    '("the 2nd", "pasta", "both", "b")\n'
    "- answer: gives a value or detail the last reply asked for (a number, a name, a "
    "place, how many), a quiz answer, or the user's own answer to check\n"
    "- react: a reaction, not a request, to a reply that asked and offered nothing "
    '("ok", "cool", "lol", "thanks", "wow", "makes sense")\n\n'
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
    # The Decider's probability that the answer needs live facts or a search was asked for;
    # None from the text read, which answers yes or no.
    live_odds: float | None = None
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
    # Whether the reply works a result out, laid out as working (``chat.decided_turn``). The
    # Decider's alone: None from the text read, and the rules decide.
    work: bool | None = None
    # How many separate results the message asks for, four standing for four or more
    # (``decider_read.ASKS_QUESTION``). The Decider's alone: None from the text read, and the
    # word rules count them (``chat.asks_turn``).
    asks: int | None = Field(default=None, ge=1, le=4)
    # After practice cards: the option the message names for each card in order ("b",
    # "other" for none of them, "none" for no answer), whether it gives that as its answer
    # ("why is 18 wrong?" names one and answers nothing), whether its one answer leaves
    # unsaid which of several cards it is for; after a lesson, whether it asks to go on. The
    # Decider's alone, asked only then (``decider_read.lesson_questions``).
    card_picks: list[str] | None = None
    answers: bool | None = None
    unplaced: bool | None = None
    goes_on: bool | None = None
    # After a reply cut off before its end, whether the message asks it to go on
    # (``decider_read.RESUME_QUESTION``). The Decider's alone, asked only then.
    resumes: bool | None = None

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
        return _known(value, FOLLOWS)

    @property
    def searches(self) -> bool:
        """The turn searches before the reply: its answer is live, or the user asked."""
        return self.live or self.asked

    @property
    def nearly_live(self) -> bool:
        """Settled, but by the Decider's odds close to live (``decider_read.NEAR_LIVE_AT``)."""
        return not self.searches and (self.live_odds or 0.0) >= NEAR_LIVE_AT

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
        (role, content)
        for message in recent or []
        if (role := getattr(message, "role", None)) in {"user", "assistant"}
        and isinstance(content := getattr(message, "content", None), str)
        and content.strip()
    ][-_EARLIER_MESSAGES:]
    return [(r, _quoted(r, t, i == len(turns) - 1)) for i, (r, t) in enumerate(turns)]


def _quoted(role: str, content: str, last: bool = False) -> str:
    """The message as the read sees it: its start, and a reply's practice cards the cut left
    out. A lesson ends on its card, past the first 400 characters: "1.2 times 10 to the 24?"
    answered one, and read without it, it was a calculation laid out as working (the owner's
    chat, 2026-11-14)."""
    limit = _LAST_REPLY_CHARS if last and role == "assistant" else _EARLIER_CHARS
    head = content[:limit]
    if role != "assistant" or len(content) <= limit:
        return head
    try:
        found = practice_cards(content)
        # What the reply says after its cards hands the turn back ("Want to try a harder
        # one, or move on to ions?"): "the first one" picks from it, not from the card.
        closing = " ".join(content[block_end_of_cards(content) :].split())[-_CLOSING_CHARS:]
    except Exception as exc:  # A reply it cannot read is quoted by its start, never a failure.
        logger.info("practice cards not quoted (%s)", type(exc).__name__)
        return head
    if not found:
        # The last reply's end too: its question or offer is there, and a "yes" or "the 2nd"
        # answers it ("…Want me to turn this into an evening routine?", past 1500 characters).
        return f"{content[: limit - _END_CHARS]} … {content[-_END_CHARS:]}" if last else head
    cut = [card for card in found if card.question not in head]
    cards = " | ".join(f"{card.question} {_lettered(card.options)}".strip() for card in cut)
    quoted = f"{head} … [practice card: {cards[:_CARD_CHARS]}]" if cards else head
    return f"{quoted} … {closing}" if closing and closing not in head else quoted


def _lettered(options: tuple[str, ...]) -> str:
    """A card's options as the app letters them: "Options: A) 17; B) 35"."""
    if not options:
        return ""
    return "Options: " + "; ".join(f"{option_letter(i)}) {o}" for i, o in enumerate(options))


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
    lesson: dict[str, dict[str, Any]] | None = None,
) -> TurnDecision | None:
    """How to handle the message; None: no read. ``model_alias`` is for measurement."""
    question = text.strip()
    if not question:
        return None
    # Imported here: SymPy pool workers import chat's readers, not the gateway.
    from app.core.redis import get_redis_client
    from app.services import quota as quota_service

    try:
        # Past the day's spend cap, or with it unreadable, nothing is read: the word rules
        # and the reply's model decide.
        redis = get_redis_client()
        if await quota_service.global_spend_exceeded(redis, settings):
            return None
    except Exception as exc:  # A read is a hint: any failure leaves the turn to the rules.
        logger.info("turn decision failed (%s)", type(exc).__name__)
        return None
    messages = decision_messages(question, earlier)
    if model_alias is not None:
        return _followed(
            await _ask(settings, model_alias, messages, settings.live_read_timeout_seconds), earlier
        )
    skip = await _unsteady_readers(redis, settings)
    if {ROUTING.decider, ROUTING.live_read, ROUTING.live_read_backup} <= skip:
        # Every model the read could ask is failing: the rules decide now, with no wait.
        return None

    text_read = asyncio.create_task(_text_read(settings, messages, skip))
    # Only a message with a number in it can be given the worked layout (``worked_turn``),
    # so only its read asks whether it works a result out.
    ask_work = any(char.isdigit() for char in question)
    try:
        if ROUTING.decider in skip:
            # The Decider's breaker is open: the text read decides, as when it refuses.
            return _followed(await text_read, earlier)
        return await _join(
            settings, text_read, messages[-1]["content"], earlier, ask_work=ask_work, lesson=lesson
        )
    finally:
        # Whatever ends the read (an answer that needs no query, the reply's wait running
        # out and cancelling it, an error), the text read and its backup stop being billed.
        text_read.cancel()


async def _join(
    settings: Settings,
    text_read: asyncio.Task[TurnDecision | None],
    state: str,
    earlier: list[tuple[str, str]],
    *,
    ask_work: bool = False,
    lesson: dict[str, dict[str, Any]] | None = None,
) -> TurnDecision | None:
    """The Decider's read, with the text read's query when it calls the turn live or asked;
    the text read's own when the Decider gives none."""
    from app.modules.chat.decider_read import decide_turn

    started = time.monotonic()
    decided = await decide_turn(
        settings,
        state,
        has_earlier=bool(earlier),
        seconds=settings.live_read_timeout_seconds,
        ask_work=ask_work,
        lesson=lesson,
    )
    if decided is None:
        # The Decider gave no answer (refused at once, at busy hours): the text read decides.
        return _followed(await text_read, earlier)
    if not (decided["live"] or decided["asked"]):
        return TurnDecision(**decided)
    # The search query is text the Decider cannot write: the text read's, begun beside it.
    # It waits no longer than the reply waits for the read, which starts later, so a slow
    # query never costs the Decider's subject and effort: the read comes back without it
    # and the reply's call searches (Claude review, 2026-11-11).
    budget = min(settings.live_read_timeout_seconds, settings.live_read_wait_seconds)
    left = budget - (time.monotonic() - started)
    try:
        read = await asyncio.wait_for(text_read, max(0.0, left))
    except TimeoutError:
        read = None
    return TurnDecision(**decided, query=read.query if read is not None else "")


async def _unsteady_readers(redis: Any, settings: Settings) -> frozenset[str]:
    """The read's models to pass over (MODEL-07): one whose breaker is open and cooling
    (``services.model_health``), and the Decider while half-open unless this turn holds its
    one probe. The text read's models share their breakers with the chat lanes on the same
    models, so their probes are the chat's to claim: half-open, they are asked."""
    from app.services import model_health

    aliases = [ROUTING.decider, ROUTING.live_read, ROUTING.live_read_backup]
    breakers = await model_health.read_breakers(redis, settings, aliases)
    skip = set(breakers.cooling)
    if ROUTING.decider in breakers.half_open and not await model_health.claim_probe(
        redis, settings, ROUTING.decider
    ):
        skip.add(ROUTING.decider)
    return frozenset(skip)


async def _text_read(
    settings: Settings, messages: list[dict[str, str]], skip: frozenset[str] = frozenset()
) -> TurnDecision | None:
    """The JSON read by the read's model, and by the backup when it refuses at once; a model
    whose breaker is open (``skip``) is passed over without the wait."""
    budget = settings.live_read_timeout_seconds
    started = time.monotonic()
    read = None
    if ROUTING.live_read not in skip:
        read = await _ask(settings, ROUTING.live_read, messages, budget)
    left = budget - (time.monotonic() - started)
    if read is None and left >= _BACKUP_MIN_SECONDS and ROUTING.live_read_backup not in skip:
        # The read's model is rate-limited upstream on 15-40% of calls at busy hours, and a
        # refusal comes back in about 0.3 s: the backup answers within the same budget.
        read = await _ask(settings, ROUTING.live_read_backup, messages, left)
    return read


def _followed(read: TurnDecision | None, earlier: list[tuple[str, str]]) -> TurnDecision | None:
    if read is not None and not earlier:
        # Nothing came before it: a problem the message states itself ("Solve 3x + 7 = 22")
        # was read as a follow-up asking to solve one.
        read.follow = "none"
    return read


async def _ask(
    settings: Settings, alias: str, messages: list[dict[str, str]], seconds: float
) -> TurnDecision | None:
    """One model's read, or None: any failure leaves the turn to the next model or the
    rules."""
    from app.gateways.structured_completion import complete_structured

    try:
        return await complete_structured(
            settings=settings,
            model_alias=alias,
            messages=messages,
            schema=TurnDecision,
            max_tokens=_MAX_TOKENS,
            timeout_seconds=seconds,
            allow_fallback=False,
            quiet_timeout=True,
            # ``_text_read`` asks its own backup (``ROUTING.live_read_backup``) after a refusal.
            refusal_fallback=False,
        )
    except Exception as exc:  # A read is a hint: any failure leaves the turn to the rules.
        logger.info("turn decision failed on %s (%s)", alias, type(exc).__name__)
        return None


def start_turn_decision(
    settings: Settings, text: str, *, recent: list[Any] | None
) -> asyncio.Task[TurnDecision | None] | None:
    """The read, started now so it runs beside the turn's prep; None when it is off.
    ``recent``: the chat's window before this message, oldest first. Search off still
    reads: the lane and the thinking come from it too."""
    if not settings.live_read_enabled:
        return None
    lesson = _lesson_questions(recent)
    return asyncio.create_task(
        read_decision(settings, text, earlier=earlier_turns(recent), lesson=lesson)
    )


def _lesson_questions(recent: list[Any] | None) -> dict[str, dict[str, Any]] | None:
    """The questions about the last reply: its cards and lesson, when it ended on either,
    and whether the message goes on with it, when it was cut off before its end."""
    try:
        cards = last_reply_cards(recent)
        lesson = active_lesson_step(list(recent or [])) is not None
    except Exception as exc:  # A read is a hint: a reply it cannot read asks nothing of it.
        logger.info("lesson questions not built (%s)", type(exc).__name__)
        return None
    questions = lesson_questions(cards, lesson=lesson)
    if follows_a_cut_off_reply(recent):
        questions = {**questions, **RESUME_QUESTION}
    return questions or None


def drop_read(task: asyncio.Task[TurnDecision | None] | None) -> None:
    """Stop a read nothing will ask any more: a turn an intercept answered, or an instant
    reply. Its two or three calls run, and are billed, until they end (MODEL-06)."""
    if task is not None and not task.done():
        task.cancel()


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
