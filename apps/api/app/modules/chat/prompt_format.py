"""Which layout, writing, and integration hints a turn's system prompt gets."""

from __future__ import annotations

from app.core.config import Settings
from app.modules import web_search as web_search_service
from app.modules.chat.continuation_subject import (
    effective_presentation_subject,
    is_new_problem_request,
)
from app.modules.chat.prompt_constants import (
    BIOLOGY_PRESENTATION_HINT,
    BREVITY_REQUEST_HINT,
    BROAD_SELF_ANSWER_HINT,
    CALLOUT_FORMAT_HINT,
    CAPABILITIES_FORMAT_HINT,
    CHART_FORMAT_HINT,
    CHEMISTRY_PRESENTATION_HINT,
    CLARIFICATION_HINT,
    COMPACT_RESPONSE_FORMAT_HINT,
    COMPARISON_FORMAT_HINT,
    CONFIRM_FOLLOW_THROUGH_HINT,
    COPY_DELIVERABLE_HINT,
    DAY_PLANNING_ANSWER_HINT,
    EMAIL_ASK_PURPOSE_HINT,
    EMAIL_DRAFT_HINT,
    FORMAT_CONTRACT,
    HOWTO_FORMAT_HINT,
    LEARNING_PLAN_HINT,
    MATH_FENCE_SAFETY_HINT,
    MATH_INTENT_HINT,
    MATH_SHORT_RESPONSE_HINT,
    MATH_SOLVER_HINT,
    MATH_TUTORING_HINT,
    MERMAID_FORMAT_HINT,
    NEW_PROBLEM_HINT,
    NON_DRAFT_TURN_HINT,
    PERSONAL_DISCLOSURE_HINT,
    PHOTO_LOOKUP_HINT,
    PHYSICS_INTENT_HINT,
    PHYSICS_REPLY_POLICY,
    PHYSICS_SHORT_HINT,
    PRIVACY_HINT,
    PROSE_WRITING_HINT,
    QUOTE_FORMAT_HINT,
    REWRITE_HINT,
    SEQUENCE_FORMAT_HINT,
    SHORT_MATH_SAFETY_HINT,
    SHORT_RESPONSE_FORMAT_HINT,
    SOCIAL_DRAFT_HINT,
    STANDING_PREFERENCE_HINT,
    STATISTICS_PRESENTATION_HINT,
    STEPS_FORMAT_HINT,
    TEACHING_HINT,
    TEACHING_SHORT_NOTE,
    TRANSLATION_FORMAT_HINT,
    UNIVERSAL_FORMAT_BASELINE,
    VERIFIED_SOLVE_SAFETY_HINT,
    VISUALIZATION_HINTS,
    WALKTHROUGH_HINT,
    WRITING_LINE_HINT,
    code_question_hint,
    draft_followup,
    draft_followup_hint,
    is_bare_writing_line,
    is_brevity_request,
    is_callout_question,
    is_capabilities_question,
    is_chart_question,
    is_howto_question,
    is_learning_plan_request,
    is_lightweight_chat_turn,
    is_mermaid_question,
    is_personal_disclosure_turn,
    is_programming_turn,
    is_quote_question,
    is_sequence_diagram_question,
    is_short_confirmation,
    is_standing_preference,
    is_structured_comparison_question,
    is_task_howto,
    is_teaching_request,
    is_underspecified_writing_request,
    is_walkthrough_request,
    learning_plan_daily_contract,
    lesson_continue_hint,
    personal_record_hint,
    programming_lesson_contract,
    writing_request_kind,
)
from app.modules.chat.prompt_constants.visuals import (
    ANSWER_PHOTO_HINT,
    IMAGE_GEN_HONESTY_HINT,
    IMAGE_GEN_UNAVAILABLE_HINT,
    WHERE_IS_PHOTO_HINT,
    is_html_ui_question,
    is_image_generation_mention,
    where_is_place,
)
from app.modules.math.reply_policy import MATH_REPLY_POLICY
from app.services import time_context as time_context_service
from app.services.day_planning import is_day_planning_question, is_day_reflection_question
from app.services.prompt_safety import wrap_untrusted
from app.services.subject_solving import detect_subject


def _subject_viz_intent(query_text: str | None) -> tuple[str | None, bool]:
    if not query_text or not query_text.strip():
        return None, False
    subject = detect_subject(query_text)
    viz_intent = (
        is_chart_question(query_text)
        or is_mermaid_question(query_text)
        or is_html_ui_question(query_text)
    )
    return subject, viz_intent


def _physics_turn(query_text: str | None) -> bool:
    """Compatibility helper for callers/tests; detection is subject-neutral."""
    return bool(query_text and detect_subject(query_text) == "physics")


def _layout_format_hint(query_text: str | None) -> str | None:
    """Turn-specific layout that must win over compact prose."""
    if not query_text:
        return None
    if is_brevity_request(query_text):
        return None
    # A requested deliverable owns its shape. For example, "write a LinkedIn
    # post comparing X and Y" is a post—not a comparison table with a post
    # awkwardly appended afterward. Its writing-specific hint handles any
    # explicit side-by-side/table request inside the deliverable.
    if writing_request_kind(query_text) is not None:
        return None
    if is_chart_question(query_text):
        return CHART_FORMAT_HINT
    if is_sequence_diagram_question(query_text):
        return SEQUENCE_FORMAT_HINT
    if is_mermaid_question(query_text):
        return MERMAID_FORMAT_HINT
    # Pasted code with "explain this" or "why does it fail" is about that code,
    # line by line, even when it says "walk me through" or "teach me".
    code_hint = code_question_hint(query_text)
    if code_hint:
        return code_hint
    # Explicit "teach me" intent owns the interaction shape. A topic may also
    # contain "vs" / "difference between", but the user asked for a lesson, not
    # a one-shot comparison table. Explicit visual requests above still win.
    if is_learning_plan_request(query_text):
        return LEARNING_PLAN_HINT
    if is_teaching_request(query_text):
        return TEACHING_HINT
    # A task ("walk me through changing a tire") is not one: it keeps how-to steps.
    if is_walkthrough_request(query_text):
        return WALKTHROUGH_HINT
    if is_structured_comparison_question(query_text):
        return COMPARISON_FORMAT_HINT
    if is_quote_question(query_text):
        return QUOTE_FORMAT_HINT
    if is_callout_question(query_text):
        return CALLOUT_FORMAT_HINT
    if is_howto_question(query_text):
        return HOWTO_FORMAT_HINT
    # A solver owns the shape of "how do I solve 2x + 5 = 17".
    if is_task_howto(query_text) and detect_subject(query_text) is None:
        return STEPS_FORMAT_HINT
    return None


def code_question_layout(query_text: str | None) -> str | None:
    """The pasted-code contract for this turn, or None. A length cap or a draft wins."""
    if not query_text or is_brevity_request(query_text):
        return None
    if writing_request_kind(query_text) is not None:
        return None
    return code_question_hint(query_text)


# Subjects whose answers are worked problems, never one thing to look at.
_NO_PHOTO_SUBJECTS = frozenset({"math", "physics", "chemistry", "statistics"})


def _may_offer_answer_photo(
    query_text: str | None,
    *,
    subject: str | None,
    writing_turn: bool,
    lesson_turn: bool,
    visual_turn: bool,
) -> bool:
    """Whether this turn could be about one thing worth seeing ("what is a capybara").

    Code, a subject problem, a lesson, a draft, a chart or day plan, a pasted
    fragment and small talk never are. Offering the photo there only confused the
    reply ("I can't see the image you're referring to").
    """
    if not query_text or not query_text.strip():
        return False
    if writing_turn or lesson_turn or visual_turn or subject in _NO_PHOTO_SUBJECTS:
        return False
    if is_lightweight_chat_turn(query_text) or is_bare_writing_line(query_text):
        return False
    return not is_programming_turn(query_text)


def _writing_format_hint(query_text: str | None) -> str | None:
    """Email / message / social / translation / prose shape. Edit stays compact."""
    if not query_text:
        return None
    kind = writing_request_kind(query_text)
    if kind in {"email", "message"}:
        if is_underspecified_writing_request(query_text):
            return EMAIL_ASK_PURPOSE_HINT
        return EMAIL_DRAFT_HINT
    if kind == "social":
        if is_underspecified_writing_request(query_text):
            return EMAIL_ASK_PURPOSE_HINT
        return SOCIAL_DRAFT_HINT
    if kind == "translation":
        return TRANSLATION_FORMAT_HINT
    if kind == "prose":
        return personal_record_hint(query_text or "") or PROSE_WRITING_HINT
    if kind == "rewrite":
        return REWRITE_HINT
    return None


def _style_format_hints(
    *,
    query_text: str | None,
    style: str,
    is_day_plan: bool,
    minimal_personal_context: bool,
    compact: bool = False,
    image_generation_enabled: bool = True,
    image_search_enabled: bool = False,
    lesson: int | None = None,
    prior_messages: list[tuple[str, str]] | None = None,
) -> list[str]:
    """Clarification / day-planning / response-format hints for non-quiz turns.

    ``lesson`` is the number of the lesson the previous reply taught: this turn
    answers its practice question or asks for more, so the lesson goes on.

    ``compact`` is for greetings and pasted fragments only — not for
    "no personal data". Ordinary questions get FORMAT_CONTRACT; math/viz
    packs are intent-gated so general knowledge does not pay ~3k tokens.
    Writing deliverables replace compact / short / FORMAT_CONTRACT so a
    paragraph ask is not also told to use bullets or a compare table.
    """
    if query_text and is_capabilities_question(query_text):
        # FORMAT_CONTRACT / COPY_DELIVERABLE / CLARIFICATION all teach
        # ```email. A "what can you do" list then opens a draft card and
        # swallows the rest of the reply.
        return [
            PRIVACY_HINT,
            UNIVERSAL_FORMAT_BASELINE,
            CAPABILITIES_FORMAT_HINT,
            MATH_FENCE_SAFETY_HINT,
        ]
    if query_text and is_standing_preference(query_text):
        # "When teaching me, explain one concept at a time…" sets how to teach;
        # there is no topic yet. With the photo hint in the prompt the model
        # once answered "I can't see the image you're referring to".
        return [
            PRIVACY_HINT,
            NON_DRAFT_TURN_HINT,
            UNIVERSAL_FORMAT_BASELINE,
            STANDING_PREFERENCE_HINT,
            MATH_FENCE_SAFETY_HINT,
        ]
    if query_text and is_personal_disclosure_turn(query_text) and not lesson:
        # A first-person update is not an invitation to generate a guide. Keep
        # the contract small and decisive so the general rich-format pack
        # cannot turn "I work at Uber..." into an unsolicited career plan.
        # Mid-lesson, "I'm confused" answers the practice question instead.
        return [
            CLARIFICATION_HINT,
            PRIVACY_HINT,
            NON_DRAFT_TURN_HINT,
            PERSONAL_DISCLOSURE_HINT,
            UNIVERSAL_FORMAT_BASELINE,
            SHORT_RESPONSE_FORMAT_HINT,
            MATH_FENCE_SAFETY_HINT,
        ]
    parts: list[str] = [CLARIFICATION_HINT, PRIVACY_HINT]
    # "make it more polite" or "asking money" goes on with the draft asked for a
    # few turns ago: the same fence, the whole draft.
    followup = draft_followup(query_text, prior_messages)
    revision_fence = followup[0] if followup else None
    writing = (
        draft_followup_hint(followup[0], drafted=followup[1])
        if followup
        else _writing_format_hint(query_text)
    )
    # Pasted code to explain or fix: its own shape, ahead of any lesson.
    code_hint = code_question_layout(query_text) if writing is None else None
    learning_plan = bool(
        query_text
        and writing is None
        and code_hint is None
        and not is_brevity_request(query_text)
        and is_learning_plan_request(query_text)
    )
    teaching = bool(
        query_text
        and writing is None
        and code_hint is None
        and not is_brevity_request(query_text)
        and is_teaching_request(query_text)
    )
    # "Help me understand recursion" is a lesson on one idea, the same shape.
    walkthrough = bool(
        query_text
        and writing is None
        and code_hint is None
        and not teaching
        and not is_brevity_request(query_text)
        and is_walkthrough_request(query_text)
    )
    # A new "teach me" starts its own lesson; otherwise the last lesson goes on.
    lesson_hint = (
        lesson_continue_hint(lesson)
        if lesson
        and not teaching
        and not walkthrough
        and not learning_plan
        and not writing
        and not code_hint
        else None
    )
    writing_kind = writing_request_kind(query_text) if query_text else None
    # A proofread is a writing request too; it only has no draft fence.
    if query_text and writing is None and writing_kind != "edit":
        parts.append(NON_DRAFT_TURN_HINT)
    _, viz_intent = _subject_viz_intent(query_text)
    subject = effective_presentation_subject(query_text, prior_messages)
    if query_text and is_short_confirmation(query_text):
        parts.append(CONFIRM_FOLLOW_THROUGH_HINT)
    if query_text and is_day_planning_question(query_text):
        parts.append(DAY_PLANNING_ANSWER_HINT)
        if is_day_reflection_question(query_text):
            parts.append(
                "This is an end-of-day reflection — keep reminders, lists, and "
                "loose ends as the main focus."
            )
    if minimal_personal_context:
        parts.append(BROAD_SELF_ANSWER_HINT)
    if style == "short":
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        # Explicit draft/prose still wins over "plain text, skip fences". A lesson
        # keeps its title, sections and quiz, only smaller.
        if writing:
            parts.append(writing)
        elif code_hint:
            # "Line by line" is an explicit shape; Short style keeps the bullets short.
            parts.append(code_hint)
        elif learning_plan:
            # An explicit multi-day roadmap needs enough room to be actionable;
            # account-level short style must not collapse it into a vague paragraph.
            parts.append(LEARNING_PLAN_HINT)
        elif teaching:
            parts.extend([TEACHING_HINT, TEACHING_SHORT_NOTE])
        elif walkthrough:
            parts.extend([WALKTHROUGH_HINT, TEACHING_SHORT_NOTE])
        elif lesson_hint:
            parts.append(TEACHING_SHORT_NOTE)
        else:
            parts.append(SHORT_RESPONSE_FORMAT_HINT)
    elif is_day_plan:
        # Day-plan used to miss math guardrails. Keep a short fence-safety
        # line so incidental `$...$` still renders; keep FORMAT_CONTRACT so
        # a day outline can use headings.
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        parts.append(writing if writing else FORMAT_CONTRACT)
    elif compact:
        # Slim/casual used to still get RESPONSE_FORMAT_HINT (tips/headings/
        # tables), so a pasted phrase became a funny essay with a clipped
        # table. ChatGPT-shaped: answer first, no invented chrome.
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        layout = _layout_format_hint(query_text)
        # Compact "plain prose" turns chart/flowchart/compare asks into a
        # joke, table, or clipped 2-node mermaid. Those turns get a fence hint.
        # Writing kinds must win the same way or "one paragraph" becomes bullets.
        winner = writing or layout
        parts.append(winner if winner else COMPACT_RESPONSE_FORMAT_HINT)
    elif writing:
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        parts.append(writing)
    else:
        parts.append(UNIVERSAL_FORMAT_BASELINE)
        parts.append(FORMAT_CONTRACT)
        if viz_intent:
            parts.append(VISUALIZATION_HINTS)
        layout = _layout_format_hint(query_text)
        if layout:
            parts.append(layout)
    if lesson_hint:
        parts.append(lesson_hint)
    # In every account style: a real photo above an answer about something to see.
    if image_search_enabled and _may_offer_answer_photo(
        query_text,
        subject=subject,
        writing_turn=bool(writing or writing_kind),
        lesson_turn=bool(teaching or walkthrough or learning_plan or lesson_hint),
        visual_turn=viz_intent or is_day_plan,
    ):
        parts.append(ANSWER_PHOTO_HINT)
        if query_text and where_is_place(query_text):
            parts.append(WHERE_IS_PHOTO_HINT)
    if query_text and is_image_generation_mention(query_text):
        parts.append(
            IMAGE_GEN_HONESTY_HINT if image_generation_enabled else IMAGE_GEN_UNAVAILABLE_HINT
        )
    if subject == "physics":
        parts.append(VERIFIED_SOLVE_SAFETY_HINT)
        if style == "short" or compact:
            parts.append(PHYSICS_SHORT_HINT)
        else:
            parts.append(PHYSICS_INTENT_HINT)
    elif subject == "math":
        parts.append(VERIFIED_SOLVE_SAFETY_HINT)
        if style == "short" or compact:
            parts.append(SHORT_MATH_SAFETY_HINT)
            parts.append(MATH_SHORT_RESPONSE_HINT)
        else:
            parts.extend([MATH_INTENT_HINT, MATH_SOLVER_HINT, MATH_TUTORING_HINT])
    elif subject == "chemistry":
        parts.append(VERIFIED_SOLVE_SAFETY_HINT)
        parts.append(CHEMISTRY_PRESENTATION_HINT)
        parts.append(MATH_FENCE_SAFETY_HINT)
    elif subject == "statistics":
        parts.append(VERIFIED_SOLVE_SAFETY_HINT)
        parts.append(STATISTICS_PRESENTATION_HINT)
        parts.append(MATH_FENCE_SAFETY_HINT)
    elif subject == "biology":
        parts.append(VERIFIED_SOLVE_SAFETY_HINT)
        parts.append(BIOLOGY_PRESENTATION_HINT)
        parts.append(MATH_FENCE_SAFETY_HINT)
    else:
        parts.append(MATH_FENCE_SAFETY_HINT)
    if query_text and is_brevity_request(query_text):
        parts.append(BREVITY_REQUEST_HINT)
    # Specialized translation/prose hints already own the shape; the copy-fence
    # contract would tell the model to wrap an article in ```copy. A translated
    # draft is still a draft.
    if revision_fence or writing_kind not in {"translation", "prose"}:
        parts.append(COPY_DELIVERABLE_HINT)
    if query_text and not revision_fence and is_bare_writing_line(query_text):
        parts.append(WRITING_LINE_HINT)
    if subject == "physics":
        parts.append(PHYSICS_REPLY_POLICY)
    elif subject == "math":
        # Keep requested detail last, after general layout and tutoring hints.
        parts.append(MATH_REPLY_POLICY)
    # After the subject policy, which forbids added examples: "one more" is a
    # request for exactly that, not for the last answer again.
    if query_text and is_new_problem_request(query_text):
        parts.append(NEW_PROBLEM_HINT)
    # Turn-derived hard contracts come after generic format/math/copy guidance
    # so smaller models cannot treat exact day coverage or a tagged example as
    # an optional style preference.
    if learning_plan and query_text:
        daily_contract = learning_plan_daily_contract(query_text)
        if daily_contract:
            parts.append(daily_contract)
    if teaching and query_text:
        code_contract = programming_lesson_contract(query_text)
        if code_contract:
            parts.append(code_contract)
    return parts


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
        parts.append(wrap_untrusted("memory", memory_block, first_party=True))
    if attachment_rag_block:
        parts.append(attachment_rag_block)
    if todos_section:
        parts.append(wrap_untrusted("schedule", todos_section, first_party=True))
    if chat_history_rag_block:
        parts.append(chat_history_rag_block)
    return parts
