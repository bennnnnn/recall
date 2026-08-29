"""Chat prompt strings and turn classifiers.

Split by domain (math, learning, format, …). Import from this package the
same way as the old ``prompt_constants`` module.
"""

from app.services.chat.prompt_constants.format import (
    CALLOUT_FORMAT_HINT,
    CHART_FORMAT_HINT,
    COMPACT_RESPONSE_FORMAT_HINT,
    COMPARISON_FORMAT_HINT,
    FORMAT_CONTRACT,
    HOWTO_FORMAT_HINT,
    INTENT_FORMAT_HINT,
    MERMAID_FORMAT_HINT,
    QUOTE_FORMAT_HINT,
    RESPONSE_FORMAT_HINT,
    SHORT_RESPONSE_FORMAT_HINT,
    STYLE_HINTS,
    TONE_FORMAT_GUARD,
    UNIVERSAL_FORMAT_BASELINE,
    is_callout_question,
    is_chart_question,
    is_comparison_question,
    is_howto_question,
    is_mermaid_question,
    is_quote_question,
)
from app.services.chat.prompt_constants.learning import (
    DAY_LEARNING_SNAPSHOT_HINT,
    QUIZ_ANSWER_HINT,
    QUIZ_RECENT_MESSAGE_LIMIT,
    VOCAB_CHAT_ANSWER_HINT,
    format_quiz_grading_hint,
)
from app.services.chat.prompt_constants.math import (
    MATH_INTENT_HINT,
    MATH_SOLVER_HINT,
    MATH_TUTORING_HINT,
    SHORT_MATH_SAFETY_HINT,
)
from app.services.chat.prompt_constants.privacy import (
    BROAD_SELF_ANSWER_HINT,
    CLARIFICATION_HINT,
    DAY_PLANNING_ANSWER_HINT,
    PRIVACY_HINT,
)
from app.services.chat.prompt_constants.routing import (
    LIGHTWEIGHT_REPLY_HINT,
    is_broad_self_question,
    is_learning_progress_question,
    is_lightweight_chat_turn,
    is_writing_deliverable_request,
    needs_rich_context,
)
from app.services.chat.prompt_constants.visuals import (
    CHEMISTRY_FENCE_HINT,
    VISUALIZATION_HINTS,
    attach_chemistry_fence_hint,
    is_html_ui_question,
)
from app.services.chat.prompt_constants.writing import (
    COPY_DELIVERABLE_HINT,
    EMAIL_DRAFT_HINT,
    WRITING_LINE_HINT,
    is_bare_writing_line,
)

__all__ = [
    "BROAD_SELF_ANSWER_HINT",
    "CALLOUT_FORMAT_HINT",
    "CHART_FORMAT_HINT",
    "CHEMISTRY_FENCE_HINT",
    "CLARIFICATION_HINT",
    "COMPACT_RESPONSE_FORMAT_HINT",
    "COMPARISON_FORMAT_HINT",
    "COPY_DELIVERABLE_HINT",
    "DAY_LEARNING_SNAPSHOT_HINT",
    "DAY_PLANNING_ANSWER_HINT",
    "EMAIL_DRAFT_HINT",
    "FORMAT_CONTRACT",
    "HOWTO_FORMAT_HINT",
    "INTENT_FORMAT_HINT",
    "LIGHTWEIGHT_REPLY_HINT",
    "MATH_INTENT_HINT",
    "MATH_SOLVER_HINT",
    "MATH_TUTORING_HINT",
    "MERMAID_FORMAT_HINT",
    "PRIVACY_HINT",
    "QUIZ_ANSWER_HINT",
    "QUIZ_RECENT_MESSAGE_LIMIT",
    "QUOTE_FORMAT_HINT",
    "RESPONSE_FORMAT_HINT",
    "SHORT_MATH_SAFETY_HINT",
    "SHORT_RESPONSE_FORMAT_HINT",
    "STYLE_HINTS",
    "TONE_FORMAT_GUARD",
    "UNIVERSAL_FORMAT_BASELINE",
    "VISUALIZATION_HINTS",
    "VOCAB_CHAT_ANSWER_HINT",
    "WRITING_LINE_HINT",
    "attach_chemistry_fence_hint",
    "format_quiz_grading_hint",
    "is_bare_writing_line",
    "is_broad_self_question",
    "is_callout_question",
    "is_chart_question",
    "is_comparison_question",
    "is_howto_question",
    "is_html_ui_question",
    "is_learning_progress_question",
    "is_lightweight_chat_turn",
    "is_mermaid_question",
    "is_quote_question",
    "is_writing_deliverable_request",
    "needs_rich_context",
]
