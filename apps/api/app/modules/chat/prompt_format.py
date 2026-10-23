"""Which layout and writing hints a turn's system prompt gets.

The style hints are ``HINT_RULES``, evaluated in order over one ``StyleTurn``. A
subject's own hints come from that subject's public file (``prompt_subjects``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.modules.chat.clarify_turn import answers_last_card, last_reply_card
from app.modules.chat.continuation_subject import (
    effective_presentation_subject,
    is_new_problem_request,
    works_on_last_reply,
)
from app.modules.chat.prompt_constants import (
    BREVITY_REQUEST_HINT,
    BROAD_SELF_ANSWER_HINT,
    CALLOUT_FORMAT_HINT,
    CAPABILITIES_FORMAT_HINT,
    CHART_FORMAT_HINT,
    CHECKLIST_FORMAT_HINT,
    CLARIFICATION_HINT,
    CLARIFY_CARD_HINT,
    COMPACT_RESPONSE_FORMAT_HINT,
    COMPARISON_FORMAT_HINT,
    CONFIRM_FOLLOW_THROUGH_HINT,
    COPY_DELIVERABLE_HINT,
    DAY_PLANNING_ANSWER_HINT,
    FORMAT_CONTRACT,
    HOWTO_FORMAT_HINT,
    LEARNING_PLAN_HINT,
    MATH_FENCE_SAFETY_HINT,
    MIXED_LENGTH_HINT,
    NEW_PROBLEM_HINT,
    NON_DRAFT_TURN_HINT,
    PERSONAL_DISCLOSURE_HINT,
    PRIVACY_HINT,
    QUIZ_FORMAT_HINT,
    QUOTE_FORMAT_HINT,
    SHORT_RESPONSE_FORMAT_HINT,
    STANDING_PREFERENCE_HINT,
    STEPS_FORMAT_HINT,
    TEACHING_HINT,
    UNIVERSAL_FORMAT_BASELINE,
    VISUALIZATION_HINTS,
    WALKTHROUGH_HINT,
    WRITING_LINE_HINT,
    ReplyLength,
    code_question_hint,
    draft_followup,
    draft_followup_hint,
    is_bare_writing_line,
    is_brevity_request,
    is_callout_question,
    is_capabilities_question,
    is_chart_question,
    is_checklist_request,
    is_howto_question,
    is_learning_plan_request,
    is_lightweight_chat_turn,
    is_mermaid_question,
    is_personal_disclosure_turn,
    is_practice_request,
    is_programming_turn,
    is_quote_question,
    is_short_confirmation,
    is_social_opener,
    is_standing_preference,
    is_structured_comparison_question,
    is_task_howto,
    is_teaching_request,
    is_walkthrough_request,
    learning_plan_daily_contract,
    mermaid_format_hint,
    programming_lesson_contract,
    reply_length,
    writing_format_hint,
    writing_request_kind,
)
from app.modules.chat.prompt_constants.answer_subject import asked_about_subject, subject_photo_hint
from app.modules.chat.prompt_constants.clarify import names_its_purpose, ranking_layout
from app.modules.chat.prompt_constants.lesson_flow import lesson_turn_hint
from app.modules.chat.prompt_constants.visuals import (
    ANSWER_PHOTO_HINT,
    IMAGE_GEN_HONESTY_HINT,
    IMAGE_GEN_UNAVAILABLE_HINT,
    WHERE_IS_PHOTO_HINT,
    is_html_ui_question,
    is_image_generation_mention,
    where_is_place,
)
from app.modules.chat.prompt_subjects import subject_closing_hints, subject_presentation_hints
from app.services.day_planning import is_day_planning_question, is_day_reflection_question
from app.services.subject_solving import detect_subject


@dataclass(frozen=True)
class PromptRule[T]:
    """An ordered prompt rule: when it applies to a turn, the text it adds."""

    applies: Callable[[T], bool]
    render: Callable[[T], Sequence[str]]


def render_rules[T](rules: Sequence[PromptRule[T]], turn: T) -> list[str]:
    """Every applying rule's text, in table order."""
    return [text for rule in rules if rule.applies(turn) for text in rule.render(turn)]


def _viz_intent(query_text: str | None) -> bool:
    if not query_text or not query_text.strip():
        return False
    return (
        is_chart_question(query_text)
        or is_mermaid_question(query_text)
        or is_html_ui_question(query_text)
    )


def _layout_format_hint(query_text: str | None, *, picks: bool = False) -> str | None:
    """Turn-specific layout that must win over compact prose."""
    if not query_text or is_brevity_request(query_text):
        return None
    # A requested deliverable owns its shape. For example, "write a LinkedIn
    # post comparing X and Y" is a post—not a comparison table with a post
    # awkwardly appended afterward. Its writing-specific hint handles any
    # explicit side-by-side/table request inside the deliverable.
    if writing_request_kind(query_text) is not None:
        return None
    if is_chart_question(query_text):
        return CHART_FORMAT_HINT
    if diagram_hint := mermaid_format_hint(query_text):
        return diagram_hint
    # Pasted code with "explain this" or "why does it fail" is about that code,
    # line by line, even when it says "walk me through" or "teach me".
    if code_hint := code_question_hint(query_text):
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
    # "Quiz me on the differences between X and Y" is cards, not a table.
    if is_practice_request(query_text):
        return QUIZ_FORMAT_HINT
    if not picks and is_structured_comparison_question(query_text):
        return COMPARISON_FORMAT_HINT
    # Before how-to: "a step-by-step moving checklist" is items to tick, not steps.
    if is_checklist_request(query_text):
        return CHECKLIST_FORMAT_HINT
    if is_quote_question(query_text):
        return QUOTE_FORMAT_HINT
    if is_callout_question(query_text):
        return CALLOUT_FORMAT_HINT
    if is_howto_question(query_text):
        return HOWTO_FORMAT_HINT
    # A solver owns the shape of "how do I solve 2x + 5 = 17".
    if is_task_howto(query_text) and detect_subject(query_text) is None:
        return STEPS_FORMAT_HINT
    if ranking := ranking_layout(query_text):  # "the best countries for business": picks
        return ranking
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


@dataclass(frozen=True)
class StyleTurn:
    """What the hint rules read about one turn, worked out once."""

    query: str  # "" when the turn has no text
    length: ReplyLength
    is_day_plan: bool
    minimal_personal_context: bool
    compact: bool
    image_generation_enabled: bool
    image_search_enabled: bool
    writing: str | None
    writing_kind: str | None
    revision_fence: str | None
    code_hint: str | None
    learning_plan: bool
    teaching: bool
    walkthrough: bool
    lesson_hint: str | None
    viz_intent: bool
    subject: str | None
    # Several requests: each one's shape is in the multi-part contract, not the turn's.
    multi: bool = False
    after_card: bool = False  # it answers the last reply's card: it never asks again
    picks: bool = False  # the card's picks: its closing "compare …" asks no table


def _style_turn(
    query_text: str | None,
    *,
    is_day_plan: bool,
    minimal_personal_context: bool,
    compact: bool,
    image_generation_enabled: bool,
    image_search_enabled: bool,
    lesson: int | None,
    outline_pick: bool = False,
    lesson_after_gap: bool = False,
    prior_messages: Sequence[tuple[str, str]] | None,
    multi: bool = False,
) -> StyleTurn:
    query = query_text or ""
    # "make it more polite" or "asking money" goes on with the draft asked for a
    # few turns ago: the same fence, the whole draft.
    followup = None if multi else draft_followup(query_text, prior_messages)
    writing = draft_followup_hint(followup[0], drafted=followup[1]) if followup else None
    writing = writing or (None if multi else writing_format_hint(query_text))
    # Pasted code to explain or fix: its own shape, ahead of any lesson.
    code_hint = code_question_layout(query_text) if writing is None and not multi else None
    open_shape = bool(query and writing is None and code_hint is None and not multi)
    open_shape = open_shape and not is_brevity_request(query)
    teaching = open_shape and is_teaching_request(query)
    learning_plan = open_shape and is_learning_plan_request(query)
    # "Help me understand recursion" is a lesson on one idea, the same shape.
    walkthrough = open_shape and not teaching and is_walkthrough_request(query)
    # A new "teach me" starts its own lesson; otherwise the last lesson goes on.
    shaped = teaching or walkthrough or learning_plan or writing or code_hint
    return StyleTurn(
        query=query,
        length=reply_length(query),
        is_day_plan=is_day_plan,
        minimal_personal_context=minimal_personal_context,
        compact=compact,
        image_generation_enabled=image_generation_enabled,
        image_search_enabled=image_search_enabled,
        writing=writing,
        writing_kind=writing_request_kind(query) if query else None,
        revision_fence=followup[0] if followup else None,
        code_hint=code_hint,
        learning_plan=learning_plan,
        teaching=teaching,
        walkthrough=walkthrough,
        lesson_hint=None
        if shaped
        else lesson_turn_hint(lesson, outline_pick=outline_pick, after_gap=lesson_after_gap),
        viz_intent=_viz_intent(query_text),
        subject=effective_presentation_subject(query_text, prior_messages),
        multi=multi,
        after_card=last_reply_card(prior_messages) is not None,
        picks=answers_last_card(query_text, prior_messages),
    )


def _always(_turn: StyleTurn) -> bool:
    return True


def _asks(check: Callable[[str], bool]) -> Callable[[StyleTurn], bool]:
    """Applies when the turn has text and ``check`` holds for it."""
    return lambda turn: bool(turn.query) and check(turn.query)


def _hints(*hints: str) -> Callable[[StyleTurn], Sequence[str]]:
    return lambda _turn: hints


def _present(text: str | None) -> list[str]:
    return [text] if text else []


_DAY_REFLECTION_HINT = (
    "This is an end-of-day reflection — keep reminders, lists, and loose ends as the main focus."
)


def _day_planning(turn: StyleTurn) -> list[str]:
    if is_day_reflection_question(turn.query):
        return [DAY_PLANNING_ANSWER_HINT, _DAY_REFLECTION_HINT]
    return [DAY_PLANNING_ANSWER_HINT]


def _format_pack(turn: StyleTurn) -> list[str]:
    """The format baseline, then the one layout the turn's shape asks for."""
    if turn.is_day_plan:
        # Day-plan used to miss math guardrails. Keep a short fence-safety
        # line so incidental `$...$` still renders; keep FORMAT_CONTRACT so
        # a day outline can use headings.
        return [UNIVERSAL_FORMAT_BASELINE, turn.writing or FORMAT_CONTRACT]
    if turn.compact:
        # Slim/casual used to still get FORMAT_CONTRACT (tips/headings/
        # tables), so a pasted phrase became a funny essay with a clipped
        # table. ChatGPT-shaped: answer first, no invented chrome.
        # Compact "plain prose" turns chart/flowchart/compare asks into a
        # joke, table, or clipped 2-node mermaid. Those turns get a fence hint.
        # Writing kinds must win the same way or "one paragraph" becomes bullets.
        layout = turn.writing or _layout_format_hint(turn.query)
        return [UNIVERSAL_FORMAT_BASELINE, layout or COMPACT_RESPONSE_FORMAT_HINT]
    if turn.writing:
        return [UNIVERSAL_FORMAT_BASELINE, turn.writing]
    viz = [VISUALIZATION_HINTS] if turn.viz_intent else []
    layout = None if turn.multi else _layout_format_hint(turn.query, picks=turn.picks)
    return [UNIVERSAL_FORMAT_BASELINE, FORMAT_CONTRACT, *viz, *_present(layout)]


def _offers_answer_photo(turn: StyleTurn) -> bool:
    """Whether this turn could be about one thing worth seeing ("what is a capybara").

    Code, a subject problem, a lesson, a draft, a chart or day plan, a pasted
    fragment, small talk and "continue" / "fix that" never are. Offering the photo
    there only confused the reply ("I can't see the image you're referring to").
    """
    # A multi-part message's photo, if it asks for one, is in its contract.
    if turn.multi or not turn.image_search_enabled or not turn.query.strip():
        return False
    if turn.writing or turn.writing_kind or turn.viz_intent or turn.is_day_plan:
        return False
    if turn.teaching or turn.walkthrough or turn.learning_plan or turn.lesson_hint:
        return False
    if turn.subject in _NO_PHOTO_SUBJECTS:
        return False
    if is_lightweight_chat_turn(turn.query) or is_social_opener(turn.query):
        return False
    if is_bare_writing_line(turn.query) or works_on_last_reply(turn.query):
        return False
    return not is_programming_turn(turn.query)


def _answer_photo(turn: StyleTurn) -> list[str]:
    if turn.query and where_is_place(turn.query):
        return [ANSWER_PHOTO_HINT, WHERE_IS_PHOTO_HINT]
    subject = asked_about_subject(turn.query)
    if subject:
        return [ANSWER_PHOTO_HINT, subject_photo_hint(subject)]
    return [ANSWER_PHOTO_HINT]


def _may_ask_with_card(turn: StyleTurn) -> bool:
    """An unshaped turn (no greeting, draft, code, lesson, problem), not a card's answer,
    and not a "best X for Y" question, which already says what it is for."""
    shaped = turn.compact or turn.multi or turn.writing or turn.code_hint or turn.lesson_hint
    lesson = turn.teaching or turn.learning_plan or turn.subject in _NO_PHOTO_SUBJECTS
    answerable = turn.after_card or names_its_purpose(turn.query)
    return bool(turn.query) and not shaped and not lesson and not answerable


HINT_RULES: tuple[PromptRule[StyleTurn], ...] = (
    PromptRule(_always, _hints(CLARIFICATION_HINT, PRIVACY_HINT)),
    PromptRule(_may_ask_with_card, _hints(CLARIFY_CARD_HINT)),
    # A proofread is a writing request too; it only has no draft fence.
    PromptRule(
        lambda t: bool(t.query) and t.writing is None and t.writing_kind != "edit" and not t.multi,
        _hints(NON_DRAFT_TURN_HINT),
    ),
    PromptRule(_asks(is_short_confirmation), _hints(CONFIRM_FOLLOW_THROUGH_HINT)),
    PromptRule(_asks(is_day_planning_question), _day_planning),
    PromptRule(lambda t: t.minimal_personal_context, _hints(BROAD_SELF_ANSWER_HINT)),
    PromptRule(_always, _format_pack),
    PromptRule(lambda t: bool(t.lesson_hint), lambda t: _present(t.lesson_hint)),
    # A real photo above an answer about something to see.
    PromptRule(_offers_answer_photo, _answer_photo),
    PromptRule(
        _asks(is_image_generation_mention),
        lambda t: [
            IMAGE_GEN_HONESTY_HINT if t.image_generation_enabled else IMAGE_GEN_UNAVAILABLE_HINT
        ],
    ),
    PromptRule(
        _always,
        lambda t: subject_presentation_hints(t.subject, short=t.compact),
    ),
    # A length cap; a cap on one part and detail on another (``length.reply_length``).
    # A multi-part message scopes a cap to its request in the multi-part contract.
    PromptRule(lambda t: not t.multi and t.length == "brief", _hints(BREVITY_REQUEST_HINT)),
    PromptRule(lambda t: t.length == "mixed", _hints(MIXED_LENGTH_HINT)),
    # Specialized translation/prose hints already own the shape; the copy-fence
    # contract would tell the model to wrap an article in ```copy. A translated
    # draft is still a draft.
    PromptRule(
        lambda t: bool(t.revision_fence) or t.writing_kind not in {"translation", "prose"},
        _hints(COPY_DELIVERABLE_HINT),
    ),
    PromptRule(
        lambda t: bool(t.query) and not t.revision_fence and is_bare_writing_line(t.query),
        _hints(WRITING_LINE_HINT),
    ),
    # Keep requested detail last, after general layout and tutoring hints.
    PromptRule(_always, lambda t: subject_closing_hints(t.subject)),
    # After the subject policy, which forbids added examples: "one more" is a
    # request for exactly that, not for the last answer again.
    PromptRule(_asks(is_new_problem_request), _hints(NEW_PROBLEM_HINT)),
    # Turn-derived hard contracts come after generic format/math/copy guidance
    # so smaller models cannot treat exact day coverage or a tagged example as
    # an optional style preference.
    PromptRule(
        lambda t: t.learning_plan, lambda t: _present(learning_plan_daily_contract(t.query))
    ),
    PromptRule(lambda t: t.teaching, lambda t: _present(programming_lesson_contract(t.query))),
)


def _exclusive_pack(
    query_text: str | None, lesson: int | None, *, outline_pick: bool = False
) -> list[str] | None:
    """The whole hint list for a turn whose kind allows nothing else, or None."""
    if not query_text:
        return None
    if is_capabilities_question(query_text):
        # FORMAT_CONTRACT / COPY_DELIVERABLE / CLARIFICATION all teach
        # ```email. A "what can you do" list then opens a draft card and
        # swallows the rest of the reply.
        return [
            PRIVACY_HINT,
            UNIVERSAL_FORMAT_BASELINE,
            CAPABILITIES_FORMAT_HINT,
            MATH_FENCE_SAFETY_HINT,
        ]
    if is_standing_preference(query_text):
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
    if is_personal_disclosure_turn(query_text) and not (lesson or outline_pick):
        # A first-person update is not an invitation to generate a guide. Keep
        # the contract small and decisive so the general rich-format pack
        # cannot turn "I work at Uber..." into an unsolicited career plan.
        # Mid-lesson, "I'm confused" answers the practice question instead, and
        # "I'm a beginner" after an outline picks where the lessons start.
        return [
            CLARIFICATION_HINT,
            PRIVACY_HINT,
            NON_DRAFT_TURN_HINT,
            PERSONAL_DISCLOSURE_HINT,
            UNIVERSAL_FORMAT_BASELINE,
            SHORT_RESPONSE_FORMAT_HINT,
            MATH_FENCE_SAFETY_HINT,
        ]
    return None


def _style_format_hints(
    *,
    query_text: str | None,
    is_day_plan: bool,
    minimal_personal_context: bool,
    compact: bool = False,
    image_generation_enabled: bool = True,
    image_search_enabled: bool = False,
    lesson: int | None = None,
    outline_pick: bool = False,
    lesson_after_gap: bool = False,
    prior_messages: Sequence[tuple[str, str]] | None = None,
    multi: bool = False,
) -> list[str]:
    """Clarification / day-planning / response-format hints for non-quiz turns.

    ``lesson`` / ``outline_pick`` / ``lesson_after_gap``: where a lesson stands
    (``prompt_constants/lesson_flow.py``). ``compact`` is for greetings and pasted
    fragments only, not "no personal data". Ordinary questions get FORMAT_CONTRACT;
    math/viz packs are intent-gated so general knowledge does not pay ~3k tokens.
    Writing deliverables replace compact / short / FORMAT_CONTRACT so a
    paragraph ask is not also told to use bullets or a compare table.
    """
    pack = None if multi else _exclusive_pack(query_text, lesson, outline_pick=outline_pick)
    if pack is not None:
        return pack
    turn = _style_turn(
        query_text,
        lesson=lesson,
        outline_pick=outline_pick,
        lesson_after_gap=lesson_after_gap,
        prior_messages=prior_messages,
        is_day_plan=is_day_plan,
        minimal_personal_context=minimal_personal_context,
        compact=compact,
        image_generation_enabled=image_generation_enabled,
        image_search_enabled=image_search_enabled,
        multi=multi,
    )
    return render_rules(HINT_RULES, turn)
