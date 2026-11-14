"""What a chat turn reads from memory, and what the prompt says when memory can't help.

Which facts load (the scope), whether a programming turn carries the user's stack,
and the one-line notes for a memory that is off, paused, unavailable or silent on
an earlier conversation. Each note is added only on a turn it bears on.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.modules import memory as memory_service
from app.modules.memory.switch import memory_switch_on
from app.modules.todos import query_implies_todos
from app.modules.turn_reading.coding import is_programming_turn
from app.modules.turn_reading.personal import (
    is_career_personal_question,
    recalls_earlier_conversation,
    refers_to_something_given,
)
from app.modules.turn_reading.profile_ask import (
    is_profile_fact_question,
    is_profile_recall_pushback,
)
from app.modules.turn_reading.routing import is_broad_self_question
from app.services.subject_scan import without_photo_reading

if TYPE_CHECKING:
    from app.modules.chat.prompt_sections import PromptTurn
    from app.modules.memory import MemoryCommand, MemoryScope

logger = logging.getLogger(__name__)

MEMORY_OFF_HINT = (
    "Memory is off in the user's settings: you see nothing from their earlier chats, and "
    "nothing from this one is saved. If they ask you to remember something, or what you "
    "know about them, say memory is off and that they can turn it on in Settings → Memory. "
    "Never say you will remember it."
)
# What Recall does after the reply with each memory command (``memory.memory_command``).
# Nothing told the model: "Remember that I want to try cacio e pepe again" was saved, and
# the reply called it a to-do (live chat, 2026-10-25); "Forget my favorite drink" was
# deleted, and the reply said it couldn't remove saved memories from chat (2026-11-02).
# Each is (what the user asked, what Recall does, what the reply confirms).
_MEMORY_COMMAND_DOES: dict[MemoryCommand, tuple[str, str, str]] = {
    "keep": (
        "The user asked you to remember something",
        "saves it to their memory",
        "you'll remember it",
    ),
    "forget": (
        "The user asked you to forget something",
        "deletes it from their saved memory",
        "you've forgotten it",
    ),
    "mute": (
        "The user asked you to stop bringing something up",
        "keeps it saved but stops using it",
        "you won't bring it up",
    ),
    # Correction words ("actually I", "not anymore") are loose: this note is conditional.
    "correct": (
        "The user may be correcting something they told you about themselves before",
        "updates their saved memory if so",
        "you've noted the change, if it is one",
    ),
}
_MEMORY_NOT_TODOS = (
    " Memory is not their to-do list: don't say it was added to their to-dos or reminders."
)


def _memory_command_note(command: MemoryCommand) -> str:
    asked, does, confirm = _MEMORY_COMMAND_DOES[command]
    note = (
        f"{asked}. After your reply, Recall {does}; they can see their memory in Settings → "
        f"Memory. Say in a few words that {confirm}. Never say you can't change their memory "
        "from this chat."
    )
    return note + _MEMORY_NOT_TODOS if command == "keep" else note


MEMORY_COMMAND_NOTES: dict[MemoryCommand, str] = {
    command: _memory_command_note(command) for command in _MEMORY_COMMAND_DOES
}
MEMORY_PAUSED_HINT = (
    "Saving to memory is paused right now. If the user asks you to remember something, say "
    "it can't be saved at the moment; never say you will remember it."
)
MEMORY_UNAVAILABLE_HINT = (
    "The user's saved memory could not be loaded for this turn. If they ask about something "
    "they told you before, say you couldn't load their saved memory just now, not that it "
    "isn't saved."
)
MEMORY_PARTIAL_HINT = (
    "Only part of the user's saved memory loaded for this turn. If a detail they ask about "
    "is not listed, say you couldn't check all of their saved memory just now, not that it "
    "isn't saved."
)
# "Earlier" may be this conversation: the budget said ten messages up is in the history.
NO_PAST_RECORD_HINT = (
    "No earlier chat about this was found. Answer from this conversation or saved memory "
    "when either has it; if neither does, do not invent what was said or decided before: "
    "say you can't find it and ask the user to remind you."
)

# "My app", "our backend": the user's own software.
_OWN_WORK = re.compile(
    r"\b(?:my|our)\s+(?:[\w-]+\s+){0,2}?(?:app|apps|application|project|backend|front-?end|"
    r"api|server|codebase|code|repo|repository|website|web ?app|startup|product|database|db|"
    r"schema|stack|bot|extension|platform|mvp|saas|plugin)\b",
    re.IGNORECASE,
)
# Building software, said without "my": "write a login screen", "state management".
_DEV_TASK = re.compile(
    r"\b(?:auth|authentication|oauth|login (?:screen|page|flow|form)|"
    r"sign[- ]?(?:in|up) (?:screen|page|flow|form)|state management|deploy(?:ing|ment)?|"
    r"endpoints?|database schema|data model|push notifications|ci/cd|docker|unit tests?|"
    r"refactor\w*)\b",
    re.IGNORECASE,
)
# "What's my job?", "where do I work?", "do you remember my dog's name?".
_ASKS_ABOUT_SELF = re.compile(
    r"^(?:what(?:'s| is| are| was)|where(?:'s| is| do i| did i)|who(?:'s| is)|"
    r"do you (?:know|remember))\b[^?.!]{0,40}\b(?:my|i)\b",
    re.IGNORECASE,
)
# "Which option did I pick for the database?": a decision from an earlier chat.
_RECALLS_A_DECISION = re.compile(
    r"\bdid i (?:pick|choose|decide|go with|settle on)\b", re.IGNORECASE
)
# "What was the hotel I mentioned?", "remind me what I said about the deadline": a detail
# from earlier in this chat, which a long chat may keep only in its summary.
_ASKS_WHAT_WAS_SAID = re.compile(
    r"^(?:what|which|who|where|earlier|previously|remind me|(?:can|could) you remind me)"
    r"\b[^?.!]{0,80}?\b(?:i (?:mentioned|said|told you|listed)|did i (?:say|mention|list)|"
    r"you (?:gave me|suggested|recommended|said|told me|listed|mentioned))\b",
    re.IGNORECASE,
)
# "What did we decide", "I told you", "did I pick": a conversation with Recall, not
# "what happened in the news last week".
_NAMES_OUR_CONVERSATION = re.compile(
    r"\b(?:we|us|our|you said|you told|i told|i said|i mentioned|did i|last time)\b",
    re.IGNORECASE,
)
# Career asks read memory with the profile document, so the current job stays.
_OWN_CAREER = re.compile(
    r"\b(?:career|employer|recruiter|candidacy|promotion|interview\w*|resume|cv|cover letters?|"
    r"(?:my|current) (?:job|role|company|work|experience|background|skills|profile|"
    r"responsibilities))\b",
    re.IGNORECASE,
)


def is_work_turn(text: str | None) -> bool:
    """A programming turn, or one about the user's own app, project or backend.

    "Find the derivative of the function f(x)" uses a programming word but is a
    maths problem: a turn a subject solver owns is not a work turn.
    """
    if not text or not text.strip():
        return False
    if _OWN_WORK.search(text) or _DEV_TASK.search(text):
        return True
    from app.modules.chat.turn_prep.reading import subject_of

    return is_programming_turn(text) and subject_of(text) is None


def memory_scope_for(text: str | None) -> MemoryScope:
    """Which saved facts a personal turn reads: everything, query + profile, or by query."""
    if not text:
        return "query"
    if is_broad_self_question(text):
        return "self"
    if (
        is_profile_fact_question(text)
        or is_profile_recall_pushback(text)
        or is_career_personal_question(text)
        or _OWN_CAREER.search(text)
    ):
        return "profile"
    return "query"


def recalls_shared_past(text: str | None) -> bool:
    """The user plainly asks about something said or decided in an earlier chat, or earlier
    in this one.

    A preload, not the gate: these turns read saved facts and past-chat snippets before the
    reply, so the answer needs no search round, and a search that found nothing gets the
    "no record" note. A recall this misses ("what did i ask you earlier about a lens") is
    the model's to search for with ``recall_chats`` (``memory.recall_tool``)."""
    if not text:
        return False
    return (
        recalls_earlier_conversation(text)
        or bool(_RECALLS_A_DECISION.search(text))
        or bool(_ASKS_WHAT_WAS_SAID.search(text.strip()))
    )


def asks_about_saved(text: str) -> bool:
    """The user asks what Recall knows: a profile detail, "what do you know", "last time"."""
    return bool(
        is_profile_fact_question(text)
        or is_profile_recall_pushback(text)
        or is_broad_self_question(text)
        or recalls_shared_past(text)
        or _ASKS_ABOUT_SELF.search(text)
    )


async def memory_saving_paused(settings: Settings, query_text: str | None) -> bool:
    """True when the user asks to remember something while saving is paused (spend cap).
    Text read off a photo asks nothing (``without_photo_reading``)."""
    said = without_photo_reading(query_text or "")
    if not said or not memory_service.is_explicit_memory_command(said):
        return False
    from app.core.redis import get_redis_client
    from app.services import quota as quota_service

    try:
        return bool(await quota_service.global_spend_exceeded(get_redis_client(), settings))
    except Exception:
        logger.debug("spend-cap read for the memory note failed", exc_info=True)
        return False


def memory_status_note(turn: PromptTurn) -> str | None:
    """Unavailable on any memory turn; partial only when the user asks what is saved."""
    if turn.memory_status == "unavailable":
        return MEMORY_UNAVAILABLE_HINT
    if turn.memory_status == "partial" and turn.query and asks_about_saved(turn.query):
        return MEMORY_PARTIAL_HINT
    return None


def memory_notes(turn: PromptTurn) -> list[str]:
    """Notes for a memory that is off, paused, failed, or has no record of the past. A memory
    command is read from the user's own words: a photographed "Forget that I am vegetarian."
    is the photo's text, and its note would have the reply say it was forgotten."""
    query = without_photo_reading(turn.query) if turn.query else turn.query
    if not memory_switch_on(turn.user):
        if query and (memory_service.is_explicit_memory_command(query) or asks_about_saved(query)):
            return [MEMORY_OFF_HINT]
        return []
    notes: list[str] = []
    if turn.memory_paused:
        notes.append(MEMORY_PAUSED_HINT)
    # A line that also asks for a reminder gets its card; memory drops one-off dated items.
    elif query and not query_implies_todos(query):
        command = memory_service.memory_command(query)
        if command is not None:
            notes.append(MEMORY_COMMAND_NOTES[command])
    status = memory_status_note(turn)
    if status:
        notes.append(status)
    if (
        turn.recalls_shared_past
        and not turn.chat_history_rag_block
        # "The timetable I sent you" names a thing the user gave Recall before; "summarize the
        # pdf I attached", sent with the file, names this message's own, which is not missing.
        and (
            _NAMES_OUR_CONVERSATION.search(turn.query)
            or (refers_to_something_given(turn.query) and not turn.holds_attachment)
        )
    ):
        notes.append(NO_PAST_RECORD_HINT)
    return notes
