"""Create a reminder from the user's words, including a clock that answers 'when?'.

A model 'Set:' line is not a save. A day without a clock is not a save. A
reply that is only '6' finishes the reminder they just described, on that day,
not earlier today.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import tzinfo as TzInfo
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.todos.schemas import RecurrenceRule
from app.modules.todos.spoken_when import find_repeat, find_when, without_spans
from app.services.draft_fences import has_draft

_NEED_A_TIME = "When should I remind you?"
_ALREADY_PASSED = "That time already passed. When should I remind you?"
_USER_CLOCK_RE = re.compile(
    r"\b(?:noon|midnight)\b"
    r"|\b\d{1,2}:\d{2}\b"
    r"|\b\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)\b"
    r"|\b\d{1,2}(?::\d{2})?\s+in\s+the\s+(?:morning|afternoon|evening)\b",
    re.IGNORECASE,
)
_CLAIM_LINE_RE = re.compile(
    r"^(?:added|set|moved|deleted|done|reopened|scheduled|saved|created|date removed)\s*:\s+\S",
    re.IGNORECASE,
)
_COLON_CLAIM_RE = re.compile(
    r"(?:got it!?\s*)?"
    r"(?:added|set|moved|deleted|done|reopened|scheduled|saved|created|date removed)\s*:\s+\S",
    re.IGNORECASE,
)
_PROSE_CLAIM_RE = re.compile(
    r"\b(?:i(?:['\u2019]ve| have)?\s+added|"
    r"i(?:['\u2019]ll| will)\s+add|"
    r"added (?:your|it|that|a reminder|to your)|"
    r"you(?:['\u2019]ll| will)\s+now (?:get|have)|"
    r"marked as done|changed to|updated!|(?:to|on) your (?:grocery|shopping) list|"
    r"(?:moved|marked|deleted|removed|pushed|rescheduled|postponed|reopened|unchecked)\s+\**\w"
    r"|checked off|(?:is|are) open again|back on your list)",
    re.IGNORECASE,
)
_DECLINE_SAVE_RE = re.compile(
    r"\b(?:i (?:set|added|saved|scheduled)|reminder (?:is |was )?set)\b",
    re.IGNORECASE,
)
_DECLINE_NEGATION_RE = re.compile(
    r"\b(?:no reminder|not set|didn(?:'|\u2019)t|did not|won(?:'|\u2019)t|will not|without)\b",
    re.IGNORECASE,
)
_CHANGE_LEADS = (
    "cancel ",
    "undo ",
    "make ",
    "change ",
    "set ",
    "put ",
    "mark ",
    "complete ",
    "finish ",
    "reopen ",
    "uncheck ",
    "delete ",
    "remove ",
    "move ",
    "reschedule ",
)
# "Remind me how to convert Celsius" asks to be taught, not reminded.
_REMIND_ME_OF_A_FACT = r"(?!\s+(?:how|what|why|who|whom|whose|which|where|whether|if)\b)"
_ADD_REQUEST_RE = re.compile(
    r"^\s*(?:(?:please|pls|plz)\s+)?(?:can (?:you|u)\s+)?(?:add|buy|get|pick up|remind me"
    + _REMIND_ME_OF_A_FACT
    + r"(?:\s+to)?)\b",
    re.IGNORECASE,
)
# Words of three letters or more ("gym", "run") that name something in a reply.
_WORD_RE = re.compile(r"[^\W\d_]{3,}")
_COMMON_WORDS = frozenset(
    {
        "about",
        "after",
        "all",
        "and",
        "any",
        "are",
        "before",
        "but",
        "can",
        "did",
        "for",
        "from",
        "get",
        "got",
        "had",
        "has",
        "have",
        "her",
        "his",
        "how",
        "into",
        "its",
        "just",
        "let",
        "may",
        "more",
        "not",
        "now",
        "off",
        "one",
        "our",
        "out",
        "some",
        "that",
        "the",
        "this",
        "too",
        "use",
        "was",
        "who",
        "why",
        "with",
        "yes",
        "you",
        "your",
    }
)
_QUESTION_TITLE_RE = re.compile(
    r"(?:that|how|what|why|who|whom|whose|which|where|whether|if)\b", re.IGNORECASE
)
_CALENDAR_RE = re.compile(r"\bcalendar\b", re.IGNORECASE)
_REMIND_ME_ANYWHERE_RE = re.compile(
    r"\b(?:(?:please|pls|plz)\s+)?(?:(?:can|could|will)\s+(?:you|u)\s+)?"
    r"remind\s+me\b(?:\s+(?:to|2)\b)?",
    re.IGNORECASE,
)
_SENTENCE_END_RE = re.compile(r"[.!?]\s+|[.!?]$")
_FILLER_RE = re.compile(r"^(?:(?:wait|ok|okay|actually|oh|no|nah|sorry|hmm)[,!.]?\s+)+")
_ASKS_WHEN_RE = re.compile(r"\b(?:when|what time|which day)\b", re.IGNORECASE)
# A reply is about the user's reminders when it says so, or confirms a dated
# one the way the app does ("Set: read — Monday, Oct 12, 8:00 AM.").
_REMINDER_TALK_RE = re.compile(
    r"\b(?:remind(?:er|ers)?|to-?dos?|to-do list|task list"
    r"|your (?:grocery list|shopping list|list|schedule|calendar))\b",
    re.IGNORECASE,
)
# "Quick reminder: it's 9/5 + 32" teaches a fact; it is not about saved reminders.
_FACT_REMINDER_RE = re.compile(
    r"\b(?:quick|friendly|gentle)\s+reminder\b\s*[\u2014\u2013:,-]", re.IGNORECASE
)
_SAVED_TALK_RE = re.compile(
    r"\b(?:your\s+(?:reminders?|to-?dos?|to-do\s+list|task\s+list|list|schedule)"
    r"|remind\s+you|reminder\s+(?:is\s+|was\s+)?set|(?:is|are|was)\s+set\s+for"
    r"|you\s+have\s+(?:\w+\s+)?(?:reminders?|to-?dos?|tasks?)"
    r"|due\s+(?:today|tomorrow|tonight)|next\s+up"
    r"|marked\s+\**[^*\n]{1,60}\**\s+as\s+(?:done|complete))\b",
    re.IGNORECASE,
)
# "Add a line …", "add a rest day", "add two more examples": a part of what
# the assistant just wrote.
_CONTENT_ADD_RE = re.compile(
    r"^\s*(?:please\s+|pls\s+)?(?:(?:can|could)\s+you\s+)?(?:also\s+)?add\s+(?:in\s+)?"
    r"(?:a|an|one|another|some|the|more|two|three|\d+)\s+(?:[\w'-]+\s+){0,2}?"
    r"(?:lines?|sentences?|paragraphs?|sections?|bullets?|points?|p\.?s\.?|emojis?|jokes?"
    r"|titles?|headings?|subheadings?|signature|greeting|examples?|comments?|columns?|rows?"
    r"|tests?|steps?|stops?|days?|nights?|breaks?|visits?|detours?|chorus|verses?|hashtags?"
    r"|captions?|quotes?|details?|links?|footnotes?|references?|citations?|questions?"
    r"|options?|slides?|ingredients?)\b",
    re.IGNORECASE,
)
_CODE_BLOCK_RE = re.compile(r"```.*?(?:```|\Z)|`[^`\n]+`", re.DOTALL)
_DATED_CLAIM_RE = re.compile(
    r"(?:^|\n|!\s*)\s*(?:added|set|moved|scheduled|saved|created)\s*:\s+[^\n]+?\s[\u2014\u2013]\s+[^\n]*"
    r"(?:\d|today|tomorrow|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|daily|weekly|weekdays|monthly)",
    re.IGNORECASE,
)
_TYPOS = {
    "tommorrow": "tomorrow",
    "tommorow": "tomorrow",
    "tomorow": "tomorrow",
    "tomorrrow": "tomorrow",
    "wekkly": "weekly",
    "wekly": "weekly",
    "weekely": "weekly",
    "tmrw": "tomorrow",
    "tmr": "tomorrow",
    "tmrow": "tomorrow",
    "tomoro": "tomorrow",
    "tonite": "tonight",
    "remimd": "remind",
    "remaind": "remind",
    "remid": "remind",
    "rmind": "remind",
    # Amharic "tomorrow" and "today" in an otherwise English line.
    "\u1290\u1308": "tomorrow",
    "\u12db\u122c": "today",
}
_ADD_LEADS = (
    "please remind me to ",
    "please remind me ",
    "can you remind me to ",
    "can you remind me ",
    "could you remind me to ",
    "could you remind me ",
    "set a reminder for ",
    "set a reminder to ",
    "set a reminder ",
    "set reminder for ",
    "set reminder ",
    "create a reminder for ",
    "create a reminder to ",
    "create a reminder ",
    "reminder: ",
    "reminder - ",
    "reminder to ",
    "reminder for ",
    "please add a to-do ",
    "please add a todo ",
    "please add a reminder to ",
    "please add a reminder ",
    "add a to-do ",
    "add a todo ",
    "add a reminder to ",
    "add a reminder ",
    "add a task ",
    "add todo ",
    "add to ",
    "add ",
    "remind me to ",
    "remind me ",
)
_REPEATS: tuple[tuple[str, RecurrenceRule], ...] = (
    ("weekdays", "weekdays"),
    ("everyday", "daily"),
    ("every day", "daily"),
    ("weekly", "weekly"),
    ("daily", "daily"),
    ("monthly", "monthly"),
)
_TRAILING_FILLER = frozenset({"for", "on"})
_TITLE_LEADS = frozenset({"to", "2", "about", "-", "\u2013", "\u2014", ":"})
_TITLE_TAILS = frozenset({"for", "on", "at", "by", "to", "-", "\u2013", "\u2014", ":"})
_NEED_TO_RE = re.compile(
    r"^(?:i\s+)?(?:need|have|got|gotta|must|should)\s+(?:to\s+)?", re.IGNORECASE
)
_LIST_PHRASE_RE = re.compile(
    r"\b(?:to|on|in)\s+my\s+(?:reminders?(?:\s+list)?|to-?dos?(?:\s+list)?|to-do\s+list|list)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SpokenAdd:
    title: str
    day: str | None
    repeat: RecurrenceRule | None
    hour: int | None
    minute: int | None


def user_named_a_clock(user_text: str | None) -> bool:
    """True when this message states a time. A model-picked hour does not count.

    "tonight at 9" states one; a bare "at 9" with no part of the day does not.
    """
    if not user_text:
        return False
    return bool(_USER_CLOCK_RE.search(user_text)) or find_when(user_text).hour is not None


def chat_add_needs_a_stated_time(user_text: str | None, due_at: datetime | None) -> bool:
    """A chat create with no user clock is not saved.

    Callers that omit the user text keep the previous fence behavior.
    """
    if user_text is None:
        return False
    if due_at is None:
        return True
    return not user_named_a_clock(user_text)


def reply_when_nothing_saved(
    text: str, user_text: str | None, *, about_reminders: bool = False
) -> str:
    """The model must not confirm a reminder the server did not save.

    Only a reply about reminders is checked: one with a reminder fence
    (``about_reminders``), or one that talks about reminders or confirms a
    dated one. "Can you add 3 + 4?" answered with "3 + 4 = 7", or an answer
    with a "Created: 1991" line, is not one.
    """
    if not (about_reminders or mentions_reminders(text) or _user_declined(user_text)):
        return text
    words = _without_code(text)
    asked = _asked_to_change_or_add(user_text)
    colon = bool(_COLON_CLAIM_RE.search(words))
    prose = bool(asked and _PROSE_CLAIM_RE.search(words))
    needs_time = bool(
        user_text
        and _ADD_REQUEST_RE.search(user_text)
        and not user_named_a_clock(user_text)
        and not adds_content(user_text)
    )
    lines = text.splitlines()
    kept = _without_claim_lines(lines)
    changed = len(kept) != len(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip() if changed else text
    asks_when = bool(_ASKS_WHEN_RE.search(cleaned))
    if needs_time:
        if asks_when and not colon and not prose:
            return cleaned
        return _NEED_A_TIME
    if _user_declined(user_text) and _DECLINE_SAVE_RE.search(cleaned):
        if not _DECLINE_NEGATION_RE.search(cleaned):
            return "I didn't set a reminder."
    if colon or prose:
        return "I didn't change your reminders."
    if changed and not cleaned.strip():
        return "I didn't change your reminders."
    if not changed:
        return text
    return cleaned


def mentions_reminders(text: str | None) -> bool:
    """A reply that talks about reminders or confirms a dated one.

    Code is not talk: a React ``todos`` array or ``done: false`` is not a reminder.
    """
    if not text:
        return False
    words = _FACT_REMINDER_RE.sub(" ", _without_code(text))
    return bool(_REMINDER_TALK_RE.search(words) or _DATED_CLAIM_RE.search(words))


def claims_a_reminder_change(text: str | None) -> bool:
    """A reply line in the app's own result shape, such as "Reopened: buy milk."."""
    if not text:
        return False
    lines = _without_code(text).splitlines()
    return len(_without_claim_lines(lines)) != len(lines)


def edits_prior_reply(subject: str, *, prior_assistant: str | None, reply: str | None) -> bool:
    """ "Add a stop in Bahir Dar on Saturday at 9am" right after a trip plan edits the plan.

    So does "remove the gym on Monday" after a workout plan: the saved "gym"
    reminder is not touched. True when the reply before this turn is not
    about saved reminders, this reply says nothing about them, and what the
    message names is part of that earlier reply. The caller checks that the
    message itself does not say reminder or task.
    """
    if not prior_assistant or about_saved_reminders(prior_assistant):
        return False
    if mentions_reminders(reply) or claims_a_reminder_change(reply):
        return False
    earlier = {word.lower() for word in _WORD_RE.findall(prior_assistant)}
    named = {word.lower() for word in _WORD_RE.findall(subject)} - _COMMON_WORDS
    return bool(named & earlier)


def about_saved_reminders(text: str | None) -> bool:
    """A reply about the user's saved reminders, as the app writes one.

    "Set: gym — Thursday, 6:00 PM.", "your reminders", "is set for Friday".
    An email headed "Reminder: assignment due Friday" is someone else's deadline.
    """
    if not text or has_draft(text):
        return False
    if "```reminder_proposal" in text:
        return True
    words = _FACT_REMINDER_RE.sub(" ", _without_code(text))
    return bool(
        _SAVED_TALK_RE.search(words)
        or _DATED_CLAIM_RE.search(words)
        or claims_a_reminder_change(text)
    )


def adds_content(user_text: str | None) -> bool:
    """ "Add a line saying the rent is paid", "add a rest day": an edit, not a task."""
    if not user_text or not _CONTENT_ADD_RE.search(user_text):
        return False
    from app.modules.todos.spoken_change import names_reminders

    return not names_reminders(user_text)


def _without_code(text: str) -> str:
    return _CODE_BLOCK_RE.sub(" ", text)


def _without_claim_lines(lines: list[str]) -> list[str]:
    """Drop "Added: …" lines outside code fences; a ``done: false`` field stays."""
    kept: list[str] = []
    in_code = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_code = not in_code
        elif not in_code and _CLAIM_LINE_RE.match(line.strip()):
            continue
        kept.append(line)
    return kept


def _user_declined(user_text: str | None) -> bool:
    from app.modules.todos.reminder_fences import explicitly_declines_reminder_creation

    return explicitly_declines_reminder_creation(user_text)


def _asked_to_change_or_add(user_text: str | None) -> bool:
    if not user_text or adds_content(user_text):
        return False
    if _ADD_REQUEST_RE.search(user_text):
        return True
    if _FILLER_RE.sub("", user_text.strip().lower()).startswith(_CHANGE_LEADS):
        return True
    from app.modules.todos.spoken_change import parse_spoken_reminder_change

    return parse_spoken_reminder_change(user_text) is not None


def parse_clock_only(user_text: str | None) -> tuple[int, int] | None:
    """A reply that is only a clock, such as '6' or '6pm'. Other words are not one."""
    raw = (user_text or "").strip()
    while raw and raw[-1] in ".!?":
        raw = raw[:-1].rstrip()
    if raw.lower().startswith("at "):
        raw = raw[3:].strip()
    if not raw:
        return None
    from app.modules.todos.reminder_fences import _parse_clock

    parsed = _parse_clock(raw, 0)
    if parsed is not None and _clock_uses_the_whole_message(raw):
        return parsed
    return _bare_hour(raw)


def parse_spoken_add(user_text: str | None) -> SpokenAdd | None:
    """An add that names a task, and maybe a day, a repeat, and a clock."""
    text = _fix_typos((user_text or "").strip())
    while text and text[-1] in ".!?":
        text = text[:-1].rstrip()
    lowered = text.lower()
    if not lowered:
        return None
    body = ""
    for lead in _ADD_LEADS:
        if lowered.startswith(lead):
            body = text[len(lead) :].strip()
            break
    if not body:
        body = _remind_me_body(text)
    if not body:
        return None
    when = find_when(body)
    spans = list(when.spans)
    repeat: RecurrenceRule | None = None
    found_repeat = find_repeat(body)
    if found_repeat is not None:
        repeat = cast(RecurrenceRule, found_repeat[0])
        spans.append(found_repeat[1])
    title = _title_of(without_spans(body, spans))
    # "Add that I'll be late" or "add a line …" adds to something, not a
    # task, "remind me how to …" asks to be taught, and "add lunch to my
    # calendar" is a calendar event.
    if (
        not title
        or _QUESTION_TITLE_RE.match(title)
        or adds_content(user_text)
        or _CALENDAR_RE.search(text)
    ):
        return None
    return SpokenAdd(
        title=title[:500], day=when.day, repeat=repeat, hour=when.hour, minute=when.minute
    )


def _remind_me_body(text: str) -> str:
    """ "pls remind me 2 call dad at 7 tonight", "sat 9am wash the car. remind me".

    The sentence that holds "remind me" is the request; when "remind me" ends
    the message, the sentence before it is.
    """
    match = _REMIND_ME_ANYWHERE_RE.search(text)
    if match is None:
        return ""
    before, after = text[: match.start()], text[match.end() :]
    near = " ".join(
        (_SENTENCE_END_RE.split(before)[-1], _SENTENCE_END_RE.split(after, maxsplit=1)[0])
    ).strip()
    if _WORD_RE.search(near):
        return near
    return " ".join((before, after)).strip(" .!?")


async def pending_add(session: AsyncSession, chat_id: UUID, current: str) -> SpokenAdd | None:
    """The add they just described, when this message is only the missing clock."""
    from app.repositories import messages as messages_repo

    rows = await messages_repo.list_recent(session, chat_id, limit=8)
    skipped_current = False
    for message in reversed(rows):
        if getattr(message, "role", None) != "user":
            continue
        body = (getattr(message, "content", None) or "").strip()
        if not skipped_current and body == current.strip():
            skipped_current = True
            continue
        if parse_clock_only(body) is not None:
            continue
        add = parse_spoken_add(body)
        if add is None or add.hour is not None or not add.day:
            return None
        return add
    return None


def due_for_add(
    add: SpokenAdd,
    *,
    user_timezone: str | None,
    now: datetime | None = None,
    hour: int | None = None,
    minute: int | None = None,
) -> datetime | None:
    """The instant they named. None when the day or the clock is missing."""
    clock_hour = add.hour if hour is None else hour
    clock_minute = add.minute if minute is None else minute
    if add.day is None or clock_hour is None or clock_minute is None:
        return None
    from app.modules.todos.reminder_fences import _due_date_for_day
    from app.services import time_context as time_context_service

    tz = time_context_service.resolve_timezone(user_timezone)
    when = now.astimezone(tz) if now is not None else _now(tz)
    day = _due_date_for_day(add.day, when)
    if day is None:
        return None
    return datetime(day.year, day.month, day.day, clock_hour, clock_minute, tzinfo=tz)


def due_is_past(
    due: datetime,
    *,
    user_timezone: str | None,
    now: datetime | None = None,
) -> bool:
    from app.services import time_context as time_context_service

    normalized = time_context_service.normalize_due_at(due, user_timezone)
    if normalized is None:
        return False
    current = now.astimezone(UTC) if now is not None else _now(UTC)
    return normalized <= current


def passed_time_reply() -> str:
    return _ALREADY_PASSED


def _now(tz: TzInfo) -> datetime:
    return datetime.now(tz)


def _fix_typos(text: str) -> str:
    parts: list[str] = []
    token: list[str] = []
    for char in text:
        if char.isalpha():
            token.append(char)
            continue
        if token:
            parts.append(_replace_token("".join(token)))
            token = []
        parts.append(char)
    if token:
        parts.append(_replace_token("".join(token)))
    return "".join(parts)


def _replace_token(token: str) -> str:
    fixed = _TYPOS.get(token.lower())
    return fixed if fixed is not None else token


def _title_of(rest: str) -> str:
    """ "to call mom", "submit the report to my reminders for", "- meet abel" → the task."""
    rest = _NEED_TO_RE.sub("", _LIST_PHRASE_RE.sub(" ", rest).strip())
    words = _title_before(rest, -1).split()
    while words and words[0].lower() in _TITLE_LEADS:
        words.pop(0)
    while words and words[-1].lower() in _TITLE_TAILS:
        words.pop()
    return " ".join(words)


def _title_before(body: str, day_at: int) -> str:
    chunk = body[:day_at] if day_at >= 0 else body
    words = []
    for word in chunk.split():
        bare = word.strip("\"'.,;:").lower()
        if not bare or any(bare == name for name, _rule in _REPEATS):
            continue
        words.append(word.strip("\"'.,;:"))
    while words and words[-1].lower() in _TRAILING_FILLER | {
        "everyday",
        "daily",
        "weekly",
        "monthly",
        "weekdays",
    }:
        words.pop()
    if (
        len(words) >= 2
        and words[-2].lower() == "every"
        and words[-1].lower()
        in {
            "day",
            "week",
            "weekday",
            "month",
        }
    ):
        del words[-2:]
    return " ".join(words).strip()


def _word_at(haystack: str, word: str) -> int:
    start = 0
    while True:
        found = haystack.find(word, start)
        if found < 0:
            return -1
        before = found == 0 or not haystack[found - 1].isalpha()
        after_at = found + len(word)
        after = after_at >= len(haystack) or not haystack[after_at].isalpha()
        if before and after:
            return found
        start = found + 1


def _clock_uses_the_whole_message(text: str) -> bool:
    """True when nothing but a clock remains. '6pm tomorrow' is not clock-only."""
    from app.modules.todos.reminder_fences import _parse_clock

    parsed_at = 0
    # _parse_clock does not report where it stopped. A clock-only message has
    # no weekday or other word after the meridiem.
    if _parse_clock(text, 0) is None:
        return False
    lowered = text.lower()
    for mark in ("am", "pm", "a.m", "p.m"):
        at = lowered.find(mark)
        if at >= 0:
            parsed_at = at + len(mark)
            break
    rest = lowered[parsed_at:].strip(" .")
    return rest == ""


def _bare_hour(text: str) -> tuple[int, int] | None:
    """'6' and '6:30' mean that hour in the evening. '18' stays 18:00."""
    compact = text.replace(" ", "")
    if not compact or not compact[0].isdigit():
        return None
    hour = 0
    index = 0
    digits = 0
    while index < len(compact) and compact[index].isdigit() and digits < 2:
        hour = hour * 10 + (ord(compact[index]) - 48)
        index += 1
        digits += 1
    minute = 0
    if index < len(compact) and compact[index] == ":":
        index += 1
        if index + 1 >= len(compact) or not (
            compact[index].isdigit() and compact[index + 1].isdigit()
        ):
            return None
        minute = (ord(compact[index]) - 48) * 10 + (ord(compact[index + 1]) - 48)
        index += 2
    if index != len(compact) or minute > 59 or hour > 23:
        return None
    if hour < 12:
        hour += 12
    if hour == 24:
        return None
    return hour, minute
