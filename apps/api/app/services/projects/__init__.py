"""Learning projects service — public re-export barrel.

Callers: ``from app.services import projects as projects_service``.
Private helpers live in submodules; import those directly when needed.
"""

from __future__ import annotations

from app.services.projects.actions import (
    MAX_PROJECT_ACTIONS_PER_TURN,
    MAX_PROJECT_ITEMS_PER_PROJECT,
    PROJECT_BLOCKED_FROM_TRANSCRIPT,
    apply_project_actions,
)
from app.services.projects.common import (
    DEFAULT_DAILY_VOCAB_GOAL,
    DEFAULT_LIST,
    LEARNING_KIND_ALIASES,
    LEARNING_PRODUCT_KINDS,
    LEARNING_TARGET_LANGUAGES,
    is_learning_product_kind,
    language_display_name,
    normalize_project_kind,
    normalize_target_language,
)
from app.services.projects.crud import (
    build_stats,
    create_learning_project,
    get_project_detail,
    group_items,
    list_projects_for_user,
)
from app.services.projects.prompt_context import (
    format_current_chapter_block,
    format_learning_overview_block,
    format_projects_block,
    load_daily_learning_summary_for_prompt,
    load_project_for_prompt,
    load_projects_for_prompt,
    load_today_learning_words_for_prompt,
)
from app.services.projects.prompts import (
    CHAT_LEARNING_HANDOFF_HINT,
    DAILY_GOAL_COMPLETE_BEHAVIOR,
    LANGUAGE_BONUS_QUIZ_RULES,
    LANGUAGE_CHAT_TUTOR_HINT,
    LANGUAGE_TUTOR_HINT,
    PROJECT_HINT,
    TRIVIA_QUIZ_FENCE_EXAMPLE,
    TRIVIA_QUIZ_FORMAT_BLOCK,
    VOCAB_CARD_FENCE_EXAMPLE,
    VOCAB_LEARNING_FORMATS_BLOCK,
    VOCAB_QUIZ_FENCE_EXAMPLE,
    VOCAB_QUIZ_FORMAT_BLOCK,
    build_language_quiz_prompt,
    language_tutor_hint,
)
from app.services.projects.quiz_context import (
    load_project_quiz_context,
    looks_like_vocab_question,
)
from app.services.projects.quiz_grading import (
    apply_deterministic_quiz_answer,
    apply_quiz_result,
)
from app.services.projects.stats import (
    count_stats,
    count_stats_by_project,
    stats_from_items,
)
from app.services.projects.sync import (
    sync_projects_from_transcript,
    transcript_implies_project_sync,
)

__all__ = [
    "CHAT_LEARNING_HANDOFF_HINT",
    "DAILY_GOAL_COMPLETE_BEHAVIOR",
    "DEFAULT_DAILY_VOCAB_GOAL",
    "DEFAULT_LIST",
    "LANGUAGE_BONUS_QUIZ_RULES",
    "LANGUAGE_CHAT_TUTOR_HINT",
    "LANGUAGE_TUTOR_HINT",
    "LEARNING_KIND_ALIASES",
    "LEARNING_PRODUCT_KINDS",
    "LEARNING_TARGET_LANGUAGES",
    "MAX_PROJECT_ACTIONS_PER_TURN",
    "MAX_PROJECT_ITEMS_PER_PROJECT",
    "PROJECT_BLOCKED_FROM_TRANSCRIPT",
    "PROJECT_HINT",
    "TRIVIA_QUIZ_FENCE_EXAMPLE",
    "TRIVIA_QUIZ_FORMAT_BLOCK",
    "VOCAB_CARD_FENCE_EXAMPLE",
    "VOCAB_LEARNING_FORMATS_BLOCK",
    "VOCAB_QUIZ_FENCE_EXAMPLE",
    "VOCAB_QUIZ_FORMAT_BLOCK",
    "apply_deterministic_quiz_answer",
    "apply_project_actions",
    "apply_quiz_result",
    "build_language_quiz_prompt",
    "build_stats",
    "count_stats",
    "count_stats_by_project",
    "create_learning_project",
    "format_current_chapter_block",
    "format_learning_overview_block",
    "format_projects_block",
    "get_project_detail",
    "group_items",
    "is_learning_product_kind",
    "language_display_name",
    "language_tutor_hint",
    "list_projects_for_user",
    "load_daily_learning_summary_for_prompt",
    "load_project_for_prompt",
    "load_project_quiz_context",
    "load_projects_for_prompt",
    "load_today_learning_words_for_prompt",
    "looks_like_vocab_question",
    "normalize_project_kind",
    "normalize_target_language",
    "stats_from_items",
    "sync_projects_from_transcript",
    "transcript_implies_project_sync",
]
