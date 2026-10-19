"""The system prompt as ordered sections, and the contracts placed beside the user turn.

Each ``PromptSection`` says when it applies to a ``PromptTurn`` and what text it adds.
The system prompt is every applying section in ``PROMPT_SECTIONS`` order, a blank line
between parts. ``NEARBY_CONTRACTS`` go in one system message just before the user turn.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.models.orm import User
from app.modules import web_search as web_search_service
from app.modules.account import profile as profile_service
from app.modules.chat.continuation_subject import is_resume_request
from app.modules.chat.json_output import JSON_OUTPUT_HINT, is_json_request
from app.modules.chat.prompt_constants import (
    ADVICE_PERSONALIZE_HINT,
    BREVITY_REQUEST_HINT,
    CAREER_PERSONALIZE_HINT,
    CODE_INK_REMINDER,
    CONTINUE_HINT,
    CORRECTION_HINT,
    EXAMPLE_PERSONALIZE_HINT,
    FACT_GROUNDING_HINT,
    LIGHTWEIGHT_REPLY_HINT,
    MATH_FENCE_SAFETY_HINT,
    PERSONAL_DISCLOSURE_HINT,
    PHOTO_LOOKUP_HINT,
    PROFILE_FACT_HINT,
    SHORT_RESPONSE_FORMAT_HINT,
    STYLE_HINTS,
    TONE_FORMAT_GUARD,
    UNCLEAR_MESSAGE_HINT,
    WEB_SEARCH_OFF_HINT,
    active_lesson_step,
    is_bare_writing_line,
    is_brevity_request,
    is_capabilities_question,
    is_career_personal_question,
    is_correction,
    is_learning_plan_request,
    is_personal_disclosure_turn,
    is_profile_fact_question,
    is_profile_recall_pushback,
    is_short_confirmation,
    is_social_opener,
    is_standing_preference,
    is_teaching_request,
    learning_plan_daily_contract,
    outline_awaits_pick,
    programming_lesson_contract,
    reply_length,
    writing_format_hint,
)
from app.modules.chat.prompt_constants.lesson_flow import lesson_after_gap
from app.modules.chat.prompt_constants.multi_part import multi_part_contract
from app.modules.chat.prompt_format import (
    PromptRule,
    _layout_format_hint,
    _style_format_hints,
    code_question_layout,
)
from app.modules.chat.prompt_memory import memory_notes, memory_status_note
from app.modules.chat.prompt_profile import (
    custom_instructions_block,
    format_user_name_only_block,
    format_user_profile_block,
    should_include_profile_email,
)
from app.modules.chat.prompt_window import FollowupSubject
from app.modules.chat.turn_plan import TurnPlan
from app.modules.chemistry.followup import CHEMISTRY_FOLLOWUP_HINT
from app.modules.math.followup import MATH_FOLLOWUP_HINT
from app.modules.math.reply_policy import MATH_REPLY_POLICY
from app.modules.physics.followup import PHYSICS_FOLLOWUP_HINT
from app.services import locale as locale_service
from app.services import response_tone as response_tone_service
from app.services import time_context as time_context_service
from app.services.day_planning import is_day_planning_question
from app.services.prompt_safety import wrap_saved_memory, wrap_untrusted


@dataclass(frozen=True)
class PromptTurn:
    """What one turn's system prompt is built from."""

    user: User
    settings: Settings
    query_text: str | None
    local_tz: str
    lightweight: bool
    # Name-only profile and no integration context: casual or not about the user.
    slim: bool
    # Memory or earlier chats may answer this turn (slim turns state them on their own).
    recall_memory: bool
    advice_memory: bool
    minimal_personal_context: bool
    prompt_location: str | None
    summary: str | None
    memory_block: str
    attachment_rag_block: str
    todos_section: str | None
    chat_history_rag_block: str
    # The completed exchange before this turn (``PromptWindow.exchange``).
    exchange: list[Any]
    followup: FollowupSubject | None
    # The separate requests the message holds (``turn_prep.intents``), when more than one.
    plan: TurnPlan | None = None
    # How the memory read went ("ok", "partial", "unavailable"); see prompt_memory.
    memory_status: str = "ok"
    # Saving to memory is paused (spend cap) on a "remember …" turn.
    memory_paused: bool = False
    # "What did we decide last time": an earlier chat may answer this turn.
    recalls_shared_past: bool = False

    @property
    def query(self) -> str:
        return self.query_text or ""

    @property
    def length_hint(self) -> str:
        # No account-wide length: each message says how long it wants ("briefly",
        # "in detail"). A stored users.response_style from an older app is ignored.
        if self.lightweight:
            return STYLE_HINTS["short"]
        return STYLE_HINTS["detailed" if reply_length(self.query) == "detailed" else "balanced"]

    @property
    def multi(self) -> bool:
        return self.plan is not None and self.plan.multi


PromptSection = PromptRule[PromptTurn]


def _always(_turn: PromptTurn) -> bool:
    return True


def _present(text: str | None) -> list[str]:
    return [text] if text else []


def _profile(turn: PromptTurn) -> list[str]:
    if turn.slim:
        return [format_user_name_only_block(turn.user)]
    return [
        format_user_profile_block(
            turn.user,
            location_override=turn.prompt_location,
            include_email=should_include_profile_email(turn.query_text),
        )
    ]


def _style_hints(turn: PromptTurn) -> list[str]:
    query = turn.query
    lesson = active_lesson_step(turn.exchange)
    outline_pick = not lesson and outline_awaits_pick(turn.exchange)
    after_gap = bool(lesson) and lesson_after_gap(turn.exchange)
    # Greetings ("good morning!", "how are you?") and pasted fragments are compact.
    # "ok" / "next" after a lesson asks for the next lesson, not a casual reply.
    compact = not (lesson or outline_pick) and bool(
        query
        and (is_bare_writing_line(query) or is_short_confirmation(query) or is_social_opener(query))
    )
    return _style_format_hints(
        query_text=turn.query_text,
        is_day_plan=bool(query and is_day_planning_question(query)),
        minimal_personal_context=turn.minimal_personal_context,
        compact=compact,
        image_generation_enabled=turn.settings.image_generation_enabled,
        image_search_enabled=turn.settings.image_search_enabled,
        lesson=lesson,
        outline_pick=outline_pick,
        lesson_after_gap=after_gap,
        prior_messages=[
            (message.role, message.content)
            for message in turn.exchange
            if message.role in {"user", "assistant"} and isinstance(message.content, str)
        ],
        multi=turn.multi,
    )


def _integrations(turn: PromptTurn) -> list[str]:
    return _integration_hints(
        settings=turn.settings,
        query_text=turn.query_text,
        local_tz=turn.local_tz,
        user_locale=turn.user.locale,
        location_for_context=turn.prompt_location or profile_service.user_location_label(turn.user),
        prompt_location=turn.prompt_location,
        memory_block=turn.memory_block,
        attachment_rag_block=turn.attachment_rag_block,
        todos_section=turn.todos_section,
        summary=turn.summary,
        chat_history_rag_block=turn.chat_history_rag_block,
    )


def _slim_memory(turn: PromptTurn) -> list[str]:
    parts = []
    if turn.memory_block:
        parts.append(wrap_saved_memory(turn.memory_block))
    return [*parts, *_present(turn.chat_history_rag_block)]


def _gives_advice(turn: PromptTurn) -> bool:
    return (
        turn.slim
        and turn.recall_memory
        and turn.advice_memory
        and not (turn.query and is_capabilities_question(turn.query))
    )


def _replied(turn: PromptTurn) -> bool:
    return any(message.role == "assistant" for message in turn.exchange)


def _resumes(turn: PromptTurn) -> bool:
    """After a reply, "continue" resumes it; in a lesson it asks for the next lesson."""
    if not is_resume_request(turn.query_text) or not _replied(turn):
        return False
    return not (active_lesson_step(turn.exchange) or outline_awaits_pick(turn.exchange))


def _advice(turn: PromptTurn) -> list[str]:
    query = turn.query
    if query and (is_profile_fact_question(query) or is_profile_recall_pushback(query)):
        # A failed memory read must not become "I don't have that yet" (memory_notes).
        return [] if memory_status_note(turn) else [PROFILE_FACT_HINT]
    if query and is_teaching_request(query):
        return [EXAMPLE_PERSONALIZE_HINT]
    if query and is_career_personal_question(query):
        return [CAREER_PERSONALIZE_HINT]
    return [ADVICE_PERSONALIZE_HINT]


PROMPT_SECTIONS: tuple[PromptSection, ...] = (
    PromptSection(_always, lambda _t: ["You are Recall, a helpful personal AI assistant."]),
    PromptSection(
        _always,
        lambda t: [
            time_context_service.format_now_awareness(t.local_tz, t.user.locale, t.query_text)
        ],
    ),
    PromptSection(_always, _profile),
    PromptSection(_always, lambda t: [t.length_hint]),
    # Lightweight/chit-chat turns skipped the math guardrails entirely,
    # so incidental `$...$` rendered as raw ```latex. A two-line fence
    # safety hint is enough — not the full math pack.
    PromptSection(
        lambda t: t.lightweight,
        lambda _t: [LIGHTWEIGHT_REPLY_HINT, SHORT_RESPONSE_FORMAT_HINT, MATH_FENCE_SAFETY_HINT],
    ),
    PromptSection(lambda t: not t.lightweight, _style_hints),
    PromptSection(
        _always,
        lambda t: [
            response_tone_service.tone_hint(getattr(t.user, "response_tone", None)),
            TONE_FORMAT_GUARD,
        ],
    ),
    # "Bo" or "gd" may be a typo, another language or a half-typed message: the
    # model, which sees the conversation, decides; no word list or length gate.
    PromptSection(_always, lambda _t: [UNCLEAR_MESSAGE_HINT]),
    # A fact that may have changed is looked up or offered, never guessed.
    PromptSection(lambda t: not t.lightweight, lambda _t: [FACT_GROUNDING_HINT]),
    PromptSection(
        # The user's own choice, not a server without search: only then point to Settings.
        lambda t: not t.lightweight and getattr(t.user, "web_search_enabled", True) is False,
        lambda _t: [WEB_SEARCH_OFF_HINT],
    ),
    PromptSection(_always, lambda t: _present(custom_instructions_block(t.user))),
    PromptSection(_always, lambda t: _present(locale_service.locale_system_hint(t.user.locale))),
    # M8: inject the rolling summary even on the slim path. A slim long thread
    # (lightweight / not rich_context) still drops everything older than the
    # recent window from the prompt — without the summary the model loses all
    # context from earlier in the conversation. The summary is already
    # computed and is just a string, so including it is free.
    PromptSection(
        lambda t: bool(t.summary),
        lambda t: [
            wrap_untrusted("conversation summary", f"Summary of earlier conversation:\n{t.summary}")
        ],
    ),
    PromptSection(lambda t: not t.slim, _integrations),
    # "Coffee near me" is a slim turn, yet it needs the place and the places layout.
    PromptSection(
        lambda t: t.slim, lambda t: slim_geo_hints(t.settings, t.query_text, t.prompt_location)
    ),
    PromptSection(lambda t: t.slim and t.recall_memory, _slim_memory),
    PromptSection(_gives_advice, _advice),
    PromptSection(_always, memory_notes),
    PromptSection(
        lambda t: t.followup == "math", lambda _t: [MATH_REPLY_POLICY, MATH_FOLLOWUP_HINT]
    ),
    PromptSection(lambda t: t.followup == "chemistry", lambda _t: [CHEMISTRY_FOLLOWUP_HINT]),
    PromptSection(lambda t: t.followup == "physics", lambda _t: [PHYSICS_FOLLOWUP_HINT]),
    # Keep the acknowledgement contract closest to the user turn. Memory and
    # integration context is appended after the style pack and can otherwise
    # tempt the model into an unsolicited plan even though no task was asked.
    PromptSection(
        lambda t: (
            bool(t.query)
            and is_personal_disclosure_turn(t.query)
            and not is_standing_preference(t.query)
        ),
        lambda _t: [PERSONAL_DISCLOSURE_HINT],
    ),
)


# Repeat only the machine-checkable turn contract immediately before the
# current user message. Smaller low-latency models follow nearby system
# constraints more reliably than a clause inside the large base prompt.
def part_shape_hints(text: str) -> list[str]:
    """One request's own length or layout: "in one sentence" binds only its request."""
    if is_brevity_request(text):
        return [BREVITY_REQUEST_HINT]
    writing = writing_format_hint(text)
    if writing:
        return [writing]
    hints = _present(_layout_format_hint(text))
    if is_learning_plan_request(text):
        hints.extend(_present(learning_plan_daily_contract(text)))
    elif is_teaching_request(text):
        hints.extend(_present(programming_lesson_contract(text)))
    return hints


def _multi_part(turn: PromptTurn) -> list[str]:
    """Every request answered, each in its own section and its own shape."""
    plan = turn.plan
    if plan is None:
        return []
    shapes = [part_shape_hints(part.text) for part in plan.parts]
    return [multi_part_contract(plan, shapes)]


# A message with several requests gets the lesson contracts per request, in its own.
NEARBY_CONTRACTS: tuple[PromptSection, ...] = (
    PromptSection(
        lambda t: bool(t.query) and not t.multi and is_learning_plan_request(t.query),
        lambda t: _present(learning_plan_daily_contract(t.query)),
    ),
    PromptSection(
        lambda t: bool(t.query) and not t.multi and is_teaching_request(t.query),
        lambda t: _present(programming_lesson_contract(t.query)),
    ),
    # Pasted code to explain or fix: the `$...$` math rule must not reach its values.
    PromptSection(
        lambda t: not t.lightweight and bool(code_question_layout(t.query_text)),
        lambda _t: [CODE_INK_REMINDER],
    ),
    # "continue" resumes the last reply; it does not start over or recap.
    PromptSection(_resumes, lambda _t: [CONTINUE_HINT]),
    # "no, I said I'm vegetarian": the correction wins over what the last reply assumed.
    PromptSection(
        lambda t: bool(t.query) and _replied(t) and is_correction(t.query),
        lambda _t: [CORRECTION_HINT],
    ),
    # Asked-for JSON is checked at finalize (``json_output``); say the shape up front.
    PromptSection(lambda t: is_json_request(t.query_text), lambda _t: [JSON_OUTPUT_HINT]),
    # Last, closest to the user turn: what the reply must hold.
    PromptSection(lambda t: t.multi, _multi_part),
)


def _geo_hints(query_text: str | None, prompt_location: str | None) -> list[str]:
    """Layout and location for a nearby, distance or local-weather question."""
    if not query_text:
        return []
    parts: list[str] = []
    if web_search_service.is_ambiguous_local_places_query(query_text):
        parts.append(web_search_service.AMBIGUOUS_NEARBY_HINT)
    elif web_search_service.is_places_list_query(query_text):
        parts.append(web_search_service.LOCAL_PLACES_FORMAT_HINT)
    elif web_search_service.is_distance_query(query_text):
        parts.append(web_search_service.GEO_DISTANCE_HINT)
    if prompt_location and web_search_service.is_geo_query(query_text):
        parts.append(web_search_service.GEO_ACTIVE_LOCATION_HINT)
    return parts


def slim_geo_hints(
    settings: Settings, query_text: str | None, prompt_location: str | None
) -> list[str]:
    """A slim turn has no profile block, so it states the location the hints point to."""
    if not settings.web_search_enabled or not query_text:
        return []
    if not web_search_service.is_geo_query(query_text):
        return []
    parts = [f"The user's current location: {prompt_location}."] if prompt_location else []
    return parts + _geo_hints(query_text, prompt_location)


def _integration_hints(
    *,
    settings: Settings,
    query_text: str | None,
    local_tz: str,
    user_locale: str | None,
    location_for_context: str | None,
    prompt_location: str | None,
    memory_block: str,
    attachment_rag_block: str,
    todos_section: str | None,
    summary: str | None,
    chat_history_rag_block: str = "",
) -> list[str]:
    """Time / web / memory / todos / summary hints."""
    parts: list[str] = [
        time_context_service.format_time_context(local_tz, user_locale, location_for_context)
    ]
    if settings.web_search_enabled:
        parts.append(web_search_service.WEB_SEARCH_HINT)
        parts.extend(_geo_hints(query_text, prompt_location))
    if settings.image_search_enabled:
        parts.append(PHOTO_LOOKUP_HINT)
    if memory_block:
        parts.append(wrap_saved_memory(memory_block))
    if attachment_rag_block:
        parts.append(attachment_rag_block)
    if todos_section:
        parts.append(wrap_untrusted("schedule", todos_section, first_party=True))
    if chat_history_rag_block:
        parts.append(chat_history_rag_block)
    return parts
