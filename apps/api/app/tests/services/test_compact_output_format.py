"""Casual/slim turns must stay ChatGPT-shaped — not a funny table essay."""

from app.services.chat.prompt_builder import _style_format_hints
from app.services.chat.prompt_constants import (
    COMPACT_RESPONSE_FORMAT_HINT,
    RESPONSE_FORMAT_HINT,
    SHORT_MATH_SAFETY_HINT,
    TONE_FORMAT_GUARD,
    UNIVERSAL_FORMAT_BASELINE,
    WRITING_LINE_HINT,
    is_bare_writing_line,
)


def test_compact_turn_skips_rich_format_pack():
    parts = _style_format_hints(
        query_text="Whoever made the best decision for me",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert COMPACT_RESPONSE_FORMAT_HINT in parts
    assert RESPONSE_FORMAT_HINT not in parts
    assert SHORT_MATH_SAFETY_HINT in parts
    joined = "\n".join(parts)
    assert "Make answers visually clear" not in joined
    assert "do not invent a topic essay" in joined.lower()


def test_compact_technical_compare_uses_table_and_conditional_code_examples():
    from app.services.chat.prompt_constants import COMPARISON_FORMAT_HINT

    parts = _style_format_hints(
        query_text="Compare Python vs Java for a beginner. Side by side on typing, syntax, and use cases.",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert COMPARISON_FORMAT_HINT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts
    joined = "\n".join(parts)
    assert "tagged code fences" in joined
    assert "only when" in joined
    assert "Never invent a 'beginner choice' section" in joined
    assert "No ## headings" not in joined


def test_compact_chart_turn_uses_vega_fence_not_plain_prose():
    from app.services.chat.prompt_constants import CHART_FORMAT_HINT

    parts = _style_format_hints(
        query_text=(
            "Make a bar chart of average monthly rainfall in Seattle: "
            "Jan 5.7, Feb 3.5, Mar 3.7, Apr 2.4, May 1.8, Jun 1.5 inches."
        ),
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert CHART_FORMAT_HINT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts
    joined = "\n".join(parts)
    assert "you CAN draw this chart" in joined
    assert "NEVER substitute a markdown table" in joined
    assert "horizontal bars" in joined
    assert "no leftover" in joined.lower() or "leftover bare numbers" in joined
    assert "no ```answer" in joined
    assert "sample data" in joined
    assert "ask ONE question for the values" in joined
    assert "No ## headings" not in joined


def test_compact_mermaid_turn_uses_flowchart_fence_not_plain_prose():
    from app.services.chat.prompt_constants import MERMAID_FORMAT_HINT

    parts = _style_format_hints(
        query_text=(
            "Draw a mermaid flowchart of making a cup of coffee, "
            "from grinding beans to drinking. Keep it to about 8 steps."
        ),
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert MERMAID_FORMAT_HINT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts
    joined = "\n".join(parts)
    assert "joke setup" in joined
    assert "Do not interview for steps" in joined
    assert 'E["Grind beans"]' in joined
    assert "No ## headings" not in joined


def test_compact_tips_turn_uses_callout_blockquotes_not_plain_prose():
    from app.services.chat.prompt_constants import CALLOUT_FORMAT_HINT

    parts = _style_format_hints(
        query_text=(
            "Give me 3 tips for staying focused while studying. "
            "Include a warning about all-nighters."
        ),
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert CALLOUT_FORMAT_HINT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts
    joined = "\n".join(parts)
    assert "> Tip:" in joined
    assert "> Warning:" in joined
    assert "No ## headings" not in joined


def test_compact_week_plan_uses_howto_lists_not_plain_prose():
    from app.services.chat.prompt_constants import HOWTO_FORMAT_HINT

    parts = _style_format_hints(
        query_text="Give me a 4-week plan to learn Spanish for travel.",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert HOWTO_FORMAT_HINT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts
    joined = "\n".join(parts)
    assert "Prefer lists over a pipe table" in joined
    assert "explicitly asks for a compact table" in joined
    assert "No ## headings" not in joined


def test_compact_spanish_week_plan_uses_howto_lists():
    from app.services.chat.prompt_constants import HOWTO_FORMAT_HINT, is_howto_question

    query = "Dame un plan de 4 semanas para aprender español"
    assert is_howto_question(query)
    parts = _style_format_hints(
        query_text=query,
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert HOWTO_FORMAT_HINT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts


def test_day_plan_still_uses_richer_format_hint():
    parts = _style_format_hints(
        query_text="plan my day",
        style="balanced",
        is_day_plan=True,
        minimal_personal_context=False,
    )
    assert RESPONSE_FORMAT_HINT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts


def test_fragment_gets_writing_line_hint():
    assert is_bare_writing_line("Whoever made the best decision for me")
    assert is_bare_writing_line("Because I said so yesterday")
    assert is_bare_writing_line("correct this sentence: I goes to store")
    assert is_bare_writing_line("Please help me proofread this paragraph")
    assert is_bare_writing_line("I want you to proofread this paragraph")
    assert not is_bare_writing_line("What is 2+2?")
    assert not is_bare_writing_line("What does proofread mean?")
    assert not is_bare_writing_line("Tell me about mitochondria")
    assert not is_bare_writing_line("Python vs Java")

    parts = _style_format_hints(
        query_text="Whoever made the best decision for me",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert WRITING_LINE_HINT in parts
    assert "Do not say you are an AI" in WRITING_LINE_HINT


def test_yes_follow_through_hint_is_not_a_greeting():
    from app.services.chat.prompt_constants import CONFIRM_FOLLOW_THROUGH_HINT

    parts = _style_format_hints(
        query_text="yes",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert CONFIRM_FOLLOW_THROUGH_HINT in parts
    assert "Carry out that offer" in CONFIRM_FOLLOW_THROUGH_HINT


def test_clarification_hint_asks_once_when_purpose_or_data_missing():
    from app.services.chat.prompt_constants import (
        CLARIFICATION_HINT,
        EMAIL_ASK_PURPOSE_HINT,
        EMAIL_DRAFT_HINT,
        is_underspecified_writing_request,
    )

    assert "escribeme un correo" in CLARIFICATION_HINT
    assert "LinkedIn" in CLARIFICATION_HINT
    assert "caption" in CLARIFICATION_HINT
    assert "ask ONE question for that purpose" in CLARIFICATION_HINT
    assert "ask ONE question for the values" in CLARIFICATION_HINT
    assert "Do not interview for steps" in CLARIFICATION_HINT
    assert is_underspecified_writing_request("write me an email")
    assert is_underspecified_writing_request("escribeme un correo")
    assert not is_underspecified_writing_request("email my boss about PTO")
    assert not is_underspecified_writing_request("write an email saying I will be late")
    assert "named a recipient" not in EMAIL_DRAFT_HINT
    assert "escribeme un correo" in EMAIL_ASK_PURPOSE_HINT


def test_writing_request_kinds_cover_each_output_shape():
    from app.services.chat.prompt_constants import writing_request_kind

    cases = {
        "Write me an email about taking Friday off": "email",
        "Message my friend saying happy birthday": "message",
        "Write a LinkedIn post announcing my new role": "social",
        "Write a short LinkedIn post comparing Python and Java": "social",
        "Rewrite my LinkedIn post": "social",
        "Translate 'see you tomorrow' into Spanish": "translation",
        "Translation: 'see you tomorrow' into Spanish": "translation",
        "Could you help me translate this into Spanish?": "translation",
        "Please, translate this": "translation",
        "Por favor, traduce esto al inglés": "translation",
        "翻译这句话": "translation",
        "翻訳してください": "translation",
        "번역해 주세요": "translation",
        "翻译理论是什么？": None,
        "翻訳とは何ですか？": None,
        "번역이란 무엇인가요?": None,
        'Translate "write me an email" into Spanish': "translation",
        "Write one paragraph about photosynthesis": "prose",
        "Write a short article comparing Python and Java": "prose",
        "Write a 500-word essay": "prose",
        "Is this sentence correct?": "edit",
        "Please help me proofread this paragraph": "edit",
        "I want you to proofread this paragraph": "edit",
        "How do I delete a LinkedIn post?": None,
        "How do I write a LinkedIn post?": None,
        (
            "How do I make it concise? Please write a LinkedIn post comparing Python and Java."
        ): "social",
        (
            "How do I revise 'This is good. Really good'? Please translate it into French."
        ): "translation",
        (
            "How do I shorten this, e.g. for LinkedIn? Please write a LinkedIn post about it."
        ): "social",
        "Explain translation in protein synthesis": None,
        "Explain how ribosomes translate mRNA": None,
        "What is grammar?": None,
        "What does proofread mean?": None,
        "What is the capital of Kenya?": None,
    }
    for query, expected in cases.items():
        assert writing_request_kind(query) == expected


def test_bare_drafts_ask_once_but_supplied_purpose_drafts_now():
    from app.services.chat.prompt_constants import is_underspecified_writing_request

    assert is_underspecified_writing_request("Message to my friend")
    assert is_underspecified_writing_request("write me an email")
    assert is_underspecified_writing_request("escribeme un correo")
    assert not is_underspecified_writing_request("Message my friend saying happy birthday")
    assert not is_underspecified_writing_request("write a vacation email to my boss")
    assert not is_underspecified_writing_request("escribeme un correo diciendo que llegare tarde")


def test_each_writing_kind_gets_only_its_relevant_format_hint():
    from app.services.chat.prompt_constants import (
        EMAIL_ASK_PURPOSE_HINT,
        EMAIL_DRAFT_HINT,
        PROSE_WRITING_HINT,
        SOCIAL_DRAFT_HINT,
        TRANSLATION_FORMAT_HINT,
        WRITING_LINE_HINT,
    )

    cases = (
        ("Message to my friend", EMAIL_ASK_PURPOSE_HINT),
        ("Message my friend saying happy birthday", EMAIL_DRAFT_HINT),
        ("Write a LinkedIn post announcing my new role", SOCIAL_DRAFT_HINT),
        ("Translate 'see you tomorrow' into Spanish", TRANSLATION_FORMAT_HINT),
        ("Write one paragraph about photosynthesis", PROSE_WRITING_HINT),
        ("Is this sentence correct?", WRITING_LINE_HINT),
    )
    specialized = {
        EMAIL_ASK_PURPOSE_HINT,
        EMAIL_DRAFT_HINT,
        PROSE_WRITING_HINT,
        SOCIAL_DRAFT_HINT,
        TRANSLATION_FORMAT_HINT,
        WRITING_LINE_HINT,
    }
    for query, expected in cases:
        parts = _style_format_hints(
            query_text=query,
            style="balanced",
            is_day_plan=False,
            minimal_personal_context=False,
            compact=True,
        )
        assert expected in parts
        assert specialized.intersection(parts) == {expected}


def test_writing_deliverable_wins_over_incidental_comparison_layout():
    from app.services.chat.prompt_constants import (
        COMPARISON_FORMAT_HINT,
        PROSE_WRITING_HINT,
        SOCIAL_DRAFT_HINT,
    )

    article = _style_format_hints(
        query_text="Write an article comparing Python vs Java",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
    )
    assert PROSE_WRITING_HINT in article
    assert COMPARISON_FORMAT_HINT not in article

    modified_article = _style_format_hints(
        query_text="Write a short article comparing Python and Java",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
    )
    assert PROSE_WRITING_HINT in modified_article
    assert COMPARISON_FORMAT_HINT not in modified_article

    post = _style_format_hints(
        query_text="Write a LinkedIn post comparing Python vs Java",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
    )
    assert SOCIAL_DRAFT_HINT in post
    assert COMPARISON_FORMAT_HINT not in post

    modified_post = _style_format_hints(
        query_text="Write a short LinkedIn post comparing Python and Java",
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
    )
    assert SOCIAL_DRAFT_HINT in modified_post
    assert COMPARISON_FORMAT_HINT not in modified_post


def test_informational_queries_do_not_receive_writing_hints():
    from app.services.chat.prompt_constants import (
        EMAIL_ASK_PURPOSE_HINT,
        SOCIAL_DRAFT_HINT,
        TRANSLATION_FORMAT_HINT,
        WRITING_LINE_HINT,
    )

    writing_hints = {
        EMAIL_ASK_PURPOSE_HINT,
        SOCIAL_DRAFT_HINT,
        TRANSLATION_FORMAT_HINT,
        WRITING_LINE_HINT,
    }
    for query in (
        "How do I delete a LinkedIn post?",
        "How do I write a LinkedIn post?",
        "Explain translation in protein synthesis",
        "Explain how ribosomes translate mRNA",
        "What is grammar?",
        "What does proofread mean?",
    ):
        parts = _style_format_hints(
            query_text=query,
            style="balanced",
            is_day_plan=False,
            minimal_personal_context=False,
            compact=True,
        )
        assert not writing_hints.intersection(parts)


def test_explicit_table_request_survives_short_and_compact_styles():
    from app.services.chat.prompt_constants import (
        COMPACT_RESPONSE_FORMAT_HINT,
        SHORT_RESPONSE_FORMAT_HINT,
        UNIVERSAL_FORMAT_BASELINE,
    )

    assert "unless the user explicitly requested one" in SHORT_RESPONSE_FORMAT_HINT
    assert "explicitly asked for a table" in COMPACT_RESPONSE_FORMAT_HINT
    assert "Honor an explicit request for a table" in UNIVERSAL_FORMAT_BASELINE


def test_translation_and_proofreading_do_not_load_private_rich_context():
    from app.services.chat.prompt_constants import needs_rich_context

    assert not needs_rich_context("Translate 'hello' into Spanish")
    assert not needs_rich_context("Is this sentence correct?")
    assert needs_rich_context("Message my wife saying I will be late")


def test_universal_baseline_bans_invented_tables_and_hooks():
    assert "Never invent a pipe table" in UNIVERSAL_FORMAT_BASELINE
    assert "timetables" in UNIVERSAL_FORMAT_BASELINE
    assert "Ah, the eternal question" in UNIVERSAL_FORMAT_BASELINE
    assert "word choice only" in TONE_FORMAT_GUARD
    assert "quotation ask" in TONE_FORMAT_GUARD
    assert "one sentence" in TONE_FORMAT_GUARD
    assert "casual preference" in TONE_FORMAT_GUARD


def test_compact_quote_turn_uses_blockquote_not_plain_prose():
    from app.services.chat.prompt_constants import (
        COMPACT_RESPONSE_FORMAT_HINT,
        QUOTE_FORMAT_HINT,
        is_quote_question,
    )

    query = "Give me a famous quote by Maya Angelou about courage, with attribution."
    assert is_quote_question(query)
    assert not is_quote_question("What's the latest stock quote for AAPL?")
    assert not is_quote_question("Compare Python vs Java")

    parts = _style_format_hints(
        query_text=query,
        style="balanced",
        is_day_plan=False,
        minimal_personal_context=False,
        compact=True,
    )
    assert QUOTE_FORMAT_HINT in parts
    assert COMPACT_RESPONSE_FORMAT_HINT not in parts
    joined = "\n".join(parts)
    assert "Never emit a ```quote fence" in joined
    assert "No ## headings" not in joined
