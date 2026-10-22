"""Everyday asks get the contract that matches what the user wants back.

A draft request gets a send-ready fence, a bare one asks what to say, a change
to the previous draft returns that draft revised, and a "ways to" question is
a list, never a draft.
"""

from __future__ import annotations

import pytest

from app.modules.chat.prompt_constants import (
    COPY_DELIVERABLE_HINT,
    FORMAT_CONTRACT,
    NON_DRAFT_TURN_HINT,
    WRITING_LINE_HINT,
    draft_followup,
    draft_followup_hint,
    is_underspecified_writing_request,
    writing_request_kind,
)
from app.modules.chat.prompt_constants.writing import (
    EMAIL_ASK_PURPOSE_HINT,
    EMAIL_DRAFT_HINT,
    REWRITE_HINT,
    SOCIAL_DRAFT_HINT,
    TRANSLATION_FORMAT_HINT,
)
from app.modules.chat.prompt_format import _style_format_hints

_TEXT_DRAFT = "```message\nHi Sam, I'm running about 15 minutes late. Sorry!\n```"
_EMAIL_DRAFT = "```email\nSubject: Sick day\n\nHi Maria,\n\nI'm taking a sick day today.\n```"
_LIST_ANSWER = "1. **Invest early** - compound growth.\n2. **Raise your income** - ask for more."


def _hints(text: str, prior: tuple[str, str] | None = None) -> list[str]:
    return _style_format_hints(
        query_text=text,
        is_day_plan=False,
        minimal_personal_context=False,
        prior_messages=[("user", prior[0]), ("assistant", prior[1])] if prior else None,
    )


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("text my boss that I'll be 20 minutes late", "message"),
        ("write a message to my landlord asking to fix the heater", "message"),
        ('answer this message: "Can you send me the report by tomorrow?"', "message"),
        ("respond to this text politely: Why didn't you call me back?", "message"),
        ('how should I reply to "we need to talk"', "message"),
        ("reply to this email: Dear customer, your order has been delayed.", "email"),
        ("answer this email: Hi Ben, can you join the client call on Monday?", "email"),
        ("write a resignation email", "email"),
        ("write a follow-up email after my job interview", "email"),
        ("write a post for facebook about my new bakery opening", "social"),
        ("make a facebook post announcing our garage sale this weekend", "social"),
        ("make this more professional: hey can u send me the files asap", "rewrite"),
        ("rewrite this to sound friendlier: Your request has been denied.", "rewrite"),
        ("make my message more polite", "rewrite"),
        ("fix the grammar: me and him goes to the store yesterday", "edit"),
        ("translate to French: Thank you for your help yesterday", "translation"),
    ],
)
def test_everyday_writing_asks_read_as_their_deliverable(text: str, kind: str) -> None:
    assert writing_request_kind(text) == kind


@pytest.mark.parametrize(
    "text",
    [
        "ways to become rich",
        "how do I reply to emails faster",
        "how do I write a good cover letter",
        'what does this message mean: "lol ngl that was lowkey fire"',
        # Nothing pasted: "it" is the previous reply, not new text to send.
        "make it shorter",
        "make it rain",
    ],
)
def test_questions_and_bare_changes_are_not_new_drafts(text: str) -> None:
    assert writing_request_kind(text) is None


@pytest.mark.parametrize(
    ("text", "bare"),
    [
        ("write me a text message to John", True),
        ("write an email to my professor", True),
        ("write a facebook post", True),
        ("write a resignation email", False),
        ("write an instagram caption for a beach sunset photo", False),
        ("reply to this email: Dear customer, your order has been delayed by 3 days.", False),
        ("write a text to my friend saying sorry I missed her party", False),
    ],
)
def test_only_a_bare_draft_ask_asks_what_to_say(text: str, bare: bool) -> None:
    assert is_underspecified_writing_request(text) is bare


@pytest.mark.parametrize(
    ("text", "hint"),
    [
        ("email my manager about taking Friday off", EMAIL_DRAFT_HINT),
        ("write a message to my mom", EMAIL_ASK_PURPOSE_HINT),
        ("write a post for facebook about my daughter's graduation", SOCIAL_DRAFT_HINT),
        ("make this more polite: Send me the money you owe me now.", REWRITE_HINT),
        ("translate this message to Spanish: I'll be home late", TRANSLATION_FORMAT_HINT),
    ],
)
def test_drafts_get_their_contract_and_never_the_no_draft_rule(text: str, hint: str) -> None:
    parts = _hints(text)
    assert hint in parts
    assert NON_DRAFT_TURN_HINT not in parts


def test_a_reply_to_an_unanswered_ask_offers_yes_and_no_drafts() -> None:
    parts = _hints('reply to this message: "Hey, are you free this weekend to help me move?"')
    assert EMAIL_DRAFT_HINT in parts
    assert "**Yes:** and **No:**" in EMAIL_DRAFT_HINT
    assert "do not answer for them" in EMAIL_DRAFT_HINT


def test_a_proofread_is_a_writing_request_without_a_draft_fence() -> None:
    parts = _hints("correct this: their going to the park tomorow")
    assert NON_DRAFT_TURN_HINT not in parts
    assert WRITING_LINE_HINT in parts


@pytest.mark.parametrize(
    ("text", "prior", "fence"),
    [
        ("make it more polite", _TEXT_DRAFT, "message"),
        ("can you make it sound friendlier?", _TEXT_DRAFT, "message"),
        ("shorter", _TEXT_DRAFT, "message"),
        ("more formal", _TEXT_DRAFT, "message"),
        ("add some emojis", _TEXT_DRAFT, "message"),
        ("give me another version", _TEXT_DRAFT, "message"),
        ("add that I'll be back tomorrow", _EMAIL_DRAFT, "email"),
        ("less formal please", _EMAIL_DRAFT, "email"),
        ("translate it to Spanish", _EMAIL_DRAFT, "email"),
        ("rewrite it", _EMAIL_DRAFT, "email"),
        # The same draft in another form: the fence follows the form asked for.
        ("Email", _TEXT_DRAFT, "email"),
        ("make it an email", _TEXT_DRAFT, "email"),
        ("as a text", _EMAIL_DRAFT, "message"),
        ("make it a facebook post", _TEXT_DRAFT, "facebook"),
    ],
)
def test_a_change_to_the_previous_draft_returns_that_draft_revised(
    text: str, prior: str, fence: str
) -> None:
    assert draft_followup(text, [("user", "draft it"), ("assistant", prior)]) == (fence, True)
    parts = _hints(text, ("draft it", prior))
    assert draft_followup_hint(fence, drafted=True) in parts
    assert COPY_DELIVERABLE_HINT in parts
    assert NON_DRAFT_TURN_HINT not in parts
    assert WRITING_LINE_HINT not in parts


@pytest.mark.parametrize(
    ("text", "prior"),
    [
        # A new draft is its own deliverable.
        ("now write a message to my mom saying I'll call her tonight", _TEXT_DRAFT),
        ("is it too long?", _TEXT_DRAFT),
        ("who won the world cup in 2022", _TEXT_DRAFT),
        # The previous reply was a list, not a draft.
        ("make it shorter", _LIST_ANSWER),
        ("tell me more about the second one", _LIST_ANSWER),
        ("email marketing tips", _TEXT_DRAFT),
        ("what is email", _TEXT_DRAFT),
    ],
)
def test_other_follow_ups_are_not_draft_revisions(text: str, prior: str) -> None:
    assert draft_followup(text, [("user", "ask"), ("assistant", prior)]) is None


def test_ways_and_tips_answers_are_bold_led_numbered_lists() -> None:
    parts = _hints("ways to become rich")
    assert FORMAT_CONTRACT in parts
    assert NON_DRAFT_TURN_HINT in parts
    assert "numbered list of about 5-8 items" in FORMAT_CONTRACT
    assert "**bold label of 2-5 words**" in FORMAT_CONTRACT
    # A long list ("list ways of becoming smart" got 10 flat items) is grouped.
    assert "Over 8 items: group them under 2-4 short ### headings" in FORMAT_CONTRACT
    assert "numbering continuing across groups" in FORMAT_CONTRACT


# The chat from the app: a message to mom, then "asking money" and "send it"
# were told not to draft, and the model refused.
_MOM_CHAT = [
    ("user", "write a message to my mom"),
    ("assistant", "Hi Mom! Hope you're having a great week. Let's catch up soon!\n\nbini"),
    ("user", "What did i ask u?"),
    ("assistant", "You asked for a message to send to your mom."),
]


@pytest.mark.parametrize(
    "text",
    ["Asking money", "asking for money", "about her birthday", "send it", "write the message"],
)
def test_a_short_answer_goes_on_with_the_message_asked_for_earlier(text: str) -> None:
    assert draft_followup(text, _MOM_CHAT) == ("message", False)
    parts = _style_format_hints(
        query_text=text,
        is_day_plan=False,
        minimal_personal_context=False,
        prior_messages=_MOM_CHAT,
    )
    assert draft_followup_hint("message", drafted=False) in parts
    assert NON_DRAFT_TURN_HINT not in parts


def test_send_and_write_the_message_are_draft_requests_never_refused() -> None:
    assert writing_request_kind("Send the message asking money") == "message"
    assert writing_request_kind("U can't write the message asking for money?") == "message"
    assert "never refuse because you cannot send" in COPY_DELIVERABLE_HINT  # safety phrase


def test_a_new_question_in_between_ends_the_draft() -> None:
    chat = [
        *_MOM_CHAT,
        ("user", "what is the tallest mountain in the world and how high is it"),
        ("assistant", "Mount Everest, 8,849 m."),
    ]
    assert draft_followup("make it shorter", chat) is None
    assert draft_followup("about the weather tomorrow", []) is None


def test_drafts_leave_out_memory_trivia() -> None:
    assert "never for the user's tastes or trivia" in EMAIL_DRAFT_HINT


def test_drafts_are_signed_with_the_users_name_never_a_placeholder() -> None:
    assert "never [Your Name]" in COPY_DELIVERABLE_HINT
    assert "not unrelated likes such as food or drinks" in COPY_DELIVERABLE_HINT


@pytest.mark.parametrize(
    ("text", "asks"),
    [
        ("what is my second language?", True),
        ("where do I live?", True),
        # A writing request that mentions the user is not a profile question.
        ("write an email to the school saying my son is sick and my name is Bini", False),
        ("rewrite my bio: I am a teacher and I live in Addis", False),
    ],
)
def test_profile_fact_question_is_a_short_ask(text: str, asks: bool) -> None:
    from app.modules.chat.prompt_constants.profile_ask import is_profile_fact_question

    assert is_profile_fact_question(text) is asks


@pytest.mark.parametrize(
    "text", ["wait whats the date today", "ok what time is it", "hey, what time is it?"]
)
def test_a_filler_word_keeps_a_local_time_question(text: str) -> None:
    from app.services import time_context

    assert time_context.is_local_now_question(text)
