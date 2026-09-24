"""Public, lazily loaded surface for the Learning domain.

Keeping this package initializer lazy lets SQLAlchemy import
``modules.learning.models`` without loading the service graph.
Chat and other features should use this surface, not repositories.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CHAT_LEARNING_HANDOFF_HINT": ("prompts", "CHAT_LEARNING_HANDOFF_HINT"),
    "DAILY_GOAL_COMPLETE_BEHAVIOR": ("prompts", "DAILY_GOAL_COMPLETE_BEHAVIOR"),
    "DEFAULT_DAILY_VOCAB_GOAL": ("common", "DEFAULT_DAILY_VOCAB_GOAL"),
    "DEFAULT_LIST": ("common", "DEFAULT_LIST"),
    "LEARNING_BLOCKED_FROM_TRANSCRIPT": ("actions", "LEARNING_BLOCKED_FROM_TRANSCRIPT"),
    "LEARNING_HINT": ("prompts", "LEARNING_HINT"),
    "LEARNING_KIND_ALIASES": ("common", "LEARNING_KIND_ALIASES"),
    "LEARNING_PRODUCT_KINDS": ("common", "LEARNING_PRODUCT_KINDS"),
    "LEARNING_TARGET_LANGUAGES": ("common", "LEARNING_TARGET_LANGUAGES"),
    "MAX_LEARNING_ACTIONS_PER_TURN": ("actions", "MAX_LEARNING_ACTIONS_PER_TURN"),
    "MAX_LEARNING_ITEMS_PER_CLASS": ("actions", "MAX_LEARNING_ITEMS_PER_CLASS"),
    "apply_learning_actions": ("actions", "apply_learning_actions"),
    "apply_quiz_result": ("quiz_grading", "apply_quiz_result"),
    "build_stats": ("crud", "build_stats"),
    "collect_learning_nudge_picks": ("nudges", "collect_learning_nudge_picks"),
    "completed_today": ("home_starters", "completed_today"),
    "count_stats": ("stats", "count_stats"),
    "count_stats_by_learning": ("stats", "count_stats_by_learning"),
    "create_learning_project": ("crud", "create_learning_project"),
    "format_current_chapter_block": ("prompt_context", "format_current_chapter_block"),
    "format_learning_block": ("prompt_context", "format_learning_block"),
    "format_learning_overview_block": ("prompt_context", "format_learning_overview_block"),
    "get_learning_detail": ("crud", "get_learning_detail"),
    "get_owned_project": ("access", "get_owned_project"),
    "group_items": ("crud", "group_items"),
    "is_learning_product_kind": ("common", "is_learning_product_kind"),
    "language_display_name": ("common", "language_display_name"),
    "language_tutor_hint": ("prompts", "language_tutor_hint"),
    "list_learning_for_user": ("crud", "list_learning_for_user"),
    "load_daily_learning_summary_for_prompt": (
        "prompt_context",
        "load_daily_learning_summary_for_prompt",
    ),
    "load_learning_classes_for_prompt": ("prompt_context", "load_learning_classes_for_prompt"),
    "load_learning_for_prompt": ("prompt_context", "load_learning_for_prompt"),
    "load_learning_home_content": ("home_starters", "load_learning_home_content"),
    "load_today_learning_words_for_prompt": (
        "prompt_context",
        "load_today_learning_words_for_prompt",
    ),
    "normalize_learning_kind": ("common", "normalize_learning_kind"),
    "normalize_target_language": ("common", "normalize_target_language"),
    "project_highlight": ("home_starters", "project_highlight"),
    "stats_from_items": ("stats", "stats_from_items"),
    "strip_learning_chat_fences": ("fences", "strip_learning_chat_fences"),
    "sync_learning_from_transcript": ("sync", "sync_learning_from_transcript"),
    "transcript_implies_learning_sync": ("sync", "transcript_implies_learning_sync"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(f"app.modules.learning.{module_name}"), attribute)
    globals()[name] = value
    return value
