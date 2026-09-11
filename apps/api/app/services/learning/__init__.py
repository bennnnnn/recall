"""Learning-domain services — public re-export barrel.

Callers: ``from app.services import learning as learning_service``.
Private helpers live in submodules; import those directly when needed.
"""

from __future__ import annotations

from app.services.learning.actions import (
    LEARNING_BLOCKED_FROM_TRANSCRIPT,
    MAX_LEARNING_ACTIONS_PER_TURN,
    MAX_LEARNING_ITEMS_PER_CLASS,
    apply_learning_actions,
)
from app.services.learning.common import (
    DEFAULT_DAILY_VOCAB_GOAL,
    DEFAULT_LIST,
    LEARNING_KIND_ALIASES,
    LEARNING_PRODUCT_KINDS,
    LEARNING_TARGET_LANGUAGES,
    is_learning_product_kind,
    language_display_name,
    normalize_learning_kind,
    normalize_target_language,
)
from app.services.learning.crud import (
    build_stats,
    create_learning_project,
    get_learning_detail,
    group_items,
    list_learning_for_user,
)
from app.services.learning.prompt_context import (
    format_current_chapter_block,
    format_learning_block,
    format_learning_overview_block,
    load_daily_learning_summary_for_prompt,
    load_learning_classes_for_prompt,
    load_learning_for_prompt,
    load_today_learning_words_for_prompt,
)
from app.services.learning.prompts import (
    CHAT_LEARNING_HANDOFF_HINT,
    DAILY_GOAL_COMPLETE_BEHAVIOR,
    LEARNING_HINT,
    language_tutor_hint,
)
from app.services.learning.quiz_grading import apply_quiz_result
from app.services.learning.stats import (
    count_stats,
    count_stats_by_learning,
    stats_from_items,
)
from app.services.learning.sync import (
    sync_learning_from_transcript,
    transcript_implies_learning_sync,
)

__all__ = [
    "CHAT_LEARNING_HANDOFF_HINT",
    "DAILY_GOAL_COMPLETE_BEHAVIOR",
    "DEFAULT_DAILY_VOCAB_GOAL",
    "DEFAULT_LIST",
    "LEARNING_BLOCKED_FROM_TRANSCRIPT",
    "LEARNING_HINT",
    "LEARNING_KIND_ALIASES",
    "LEARNING_PRODUCT_KINDS",
    "LEARNING_TARGET_LANGUAGES",
    "MAX_LEARNING_ACTIONS_PER_TURN",
    "MAX_LEARNING_ITEMS_PER_CLASS",
    "apply_learning_actions",
    "apply_quiz_result",
    "build_stats",
    "count_stats",
    "count_stats_by_learning",
    "create_learning_project",
    "format_current_chapter_block",
    "format_learning_block",
    "format_learning_overview_block",
    "get_learning_detail",
    "group_items",
    "is_learning_product_kind",
    "language_display_name",
    "language_tutor_hint",
    "list_learning_for_user",
    "load_daily_learning_summary_for_prompt",
    "load_learning_classes_for_prompt",
    "load_learning_for_prompt",
    "load_today_learning_words_for_prompt",
    "normalize_learning_kind",
    "normalize_target_language",
    "stats_from_items",
    "sync_learning_from_transcript",
    "transcript_implies_learning_sync",
]
