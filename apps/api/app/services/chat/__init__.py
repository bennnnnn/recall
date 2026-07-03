"""Chat turn orchestration — prompt build, stream, finalize, background jobs."""

from app.core import jobs
from app.core.db import SessionLocal
from app.gateways import litellm_gateway
from app.repositories import chats as chats_repo
from app.repositories import messages as messages_repo
from app.repositories import usage as usage_repo
from app.repositories import users as users_repo
from app.services import attachment_lifecycle, model_catalog
from app.services import calendar as calendar_service
from app.services import chat_tools as chat_tools_service
from app.services import email as email_service
from app.services import locale as locale_service
from app.services import math_fence as math_fence_service
from app.services import math_tools as math_tools_service
from app.services import memory as memory_service
from app.services import plan as plan_service
from app.services import projects as projects_service
from app.services import quota as quota_service
from app.services import response_tone as response_tone_service
from app.services import time_context as time_context_service
from app.services import todos as todos_service
from app.services import web_search as web_search_service
from app.services.chat.post_turn import (
    enqueue_post_turn_jobs,
    finalize_stream_turn_db,
    restore_regenerate_backup,
    seed_usage_from_db,
)
from app.services.chat.prompt_builder import (
    StreamStatusFn,
    _augment_web_and_tools,
    build_prompt_messages,
    format_user_name_only_block,
    format_user_profile_block,
)
from app.services.chat.prompt_constants import (
    is_broad_self_question,
    is_writing_deliverable_request,
    max_output_tokens_for_style,
)
from app.services.chat.stream import (
    stream_and_finalize,
    stream_chat_response,
    stream_edit_response,
    stream_regenerate_response,
)
from app.services.chat.turn_prep import (
    RegenerateBackup,
    StreamContext,
    count_image_attachments,
    prepare_chat_turn,
    resolve_client_geo,
    vision_reserve_tokens,
)
from app.services.context_window import estimate_tokens

# Backward-compatible private aliases (tests patch these on the package).
_prepare_chat_turn = prepare_chat_turn
_stream_and_finalize = stream_and_finalize
_restore_regenerate_backup = restore_regenerate_backup
_seed_usage_from_db = seed_usage_from_db
_finalize_stream_turn_db = finalize_stream_turn_db
_enqueue_post_turn_jobs = enqueue_post_turn_jobs
_RegenerateBackup = RegenerateBackup
_StreamContext = StreamContext
_resolve_client_geo = resolve_client_geo
_count_image_attachments = count_image_attachments
_vision_reserve_tokens = vision_reserve_tokens

__all__ = [
    "SessionLocal",
    "StreamStatusFn",
    "_augment_web_and_tools",
    "_prepare_chat_turn",
    "_restore_regenerate_backup",
    "_stream_and_finalize",
    "attachment_lifecycle",
    "build_prompt_messages",
    "calendar_service",
    "chat_tools_service",
    "chats_repo",
    "email_service",
    "estimate_tokens",
    "format_user_name_only_block",
    "format_user_profile_block",
    "is_broad_self_question",
    "is_writing_deliverable_request",
    "jobs",
    "litellm_gateway",
    "locale_service",
    "math_fence_service",
    "math_tools_service",
    "max_output_tokens_for_style",
    "memory_service",
    "messages_repo",
    "model_catalog",
    "plan_service",
    "projects_service",
    "quota_service",
    "response_tone_service",
    "stream_chat_response",
    "stream_edit_response",
    "stream_regenerate_response",
    "time_context_service",
    "todos_service",
    "usage_repo",
    "users_repo",
    "web_search_service",
]
