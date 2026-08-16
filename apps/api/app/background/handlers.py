"""Job-type → handler registration for the durable job queue.

`app/core/jobs.py` owns the queue mechanics (stream, retries, DLQ, metrics)
and exposes `register`; the domain bodies live here, next to the background
modules they call. Keeping this out of `core/` means the lowest layer no
longer imports `app.background` / `app.services`, so importing the queue
does not drag every background module (and its transitive service imports)
into the graph — and adding or deleting a job touches one file that no other
job's feature branch is also editing.

Import this module once at startup, before the worker starts consuming
(`app/main.py` and `app/worker_main.py` do). Registration is an explicit
list, not import-time discovery, so the set of live job types stays greppable.
"""

import asyncio
import logging
from typing import Any
from uuid import UUID

from app.background import (
    attachment_indexing,
    compaction,
    gmail_sync,
    memory_consolidation,
    memory_extraction,
    project_sync,
    suggestion_generation,
    todo_sync,
    topic_generation,
)
from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.jobs import JobDiscardError, enqueue, register
from app.core.redis import get_redis_client
from app.services import transactional_email as transactional_email_service

logger = logging.getLogger(__name__)


async def _handle_topic(settings: Settings, payload: dict[str, Any]) -> None:
    user_id_raw = payload.get("user_id")
    user_id = UUID(user_id_raw) if user_id_raw else None
    await topic_generation.generate_chat_title(
        settings,
        UUID(payload["chat_id"]),
        payload.get("user_message", ""),
        payload.get("assistant_message", ""),
        user_id=user_id,
    )


_MEMORY_LOCK_MAX_RETRIES = 3
# Match core.jobs._RETRY_BACKOFF_S. Instant re-enqueue cannot outlast a lock
# held for an LLM round-trip; the worker is not latency-sensitive.
_MEMORY_LOCK_RETRY_BACKOFF_S = 2.0


def _memory_lock_retries(payload: dict[str, Any]) -> int:
    try:
        return int(payload.get("lock_retries") or 0)
    except (TypeError, ValueError):
        return 0


async def _reenqueue_after_memory_lock(
    *,
    job_type: str,
    retry_payload: dict[str, Any],
    dedupe_stem: str,
    warning: str,
) -> None:
    """Re-enqueue a lock-busy memory job, or discard to the DLQ after the cap.

    Each attempt uses its own ``dedupe_key`` (``{stem}:lock{n}``) so a
    reclaim of this entry plus the retry cannot double-run the same pass.
    Exhausted retries raise ``JobDiscardError`` so the worker records the
    drop in the DLQ instead of acking a silent success.
    """
    retries = _memory_lock_retries(retry_payload)
    if retries >= _MEMORY_LOCK_MAX_RETRIES:
        logger.warning("%s", warning)
        raise JobDiscardError(warning)

    next_retries = retries + 1
    await asyncio.sleep(_MEMORY_LOCK_RETRY_BACKOFF_S * next_retries)
    await enqueue(
        get_redis_client(),
        job_type,
        {**retry_payload, "lock_retries": next_retries},
        dedupe_key=f"{dedupe_stem}:lock{next_retries}",
    )


async def _handle_memory(settings: Settings, payload: dict[str, Any]) -> None:
    outcome = await memory_extraction.extract_and_store_memories(
        settings,
        user_id=UUID(payload["user_id"]),
        chat_id=UUID(payload["chat_id"]),
        transcript=payload["transcript"],
    )
    if outcome != "skipped_lock":
        return
    # Write lock busy (consolidation or sibling extraction). Re-enqueue a
    # bounded number of times so the turn's memory isn't silently dropped.
    await _reenqueue_after_memory_lock(
        job_type="memory",
        retry_payload={
            "user_id": payload["user_id"],
            "chat_id": payload["chat_id"],
            "transcript": payload["transcript"],
            "lock_retries": payload.get("lock_retries") or 0,
        },
        dedupe_stem=f"memory:{payload['user_id']}:{payload['chat_id']}",
        warning=(
            "Memory extraction dropped after lock retries "
            f"user_id={payload.get('user_id')} chat_id={payload.get('chat_id')}"
        ),
    )


async def _handle_memory_consolidate(settings: Settings, payload: dict[str, Any]) -> None:
    outcome = await memory_consolidation.consolidate_user_memory_sections(
        settings,
        user_id=UUID(payload["user_id"]),
    )
    if outcome != "skipped_lock":
        return
    await _reenqueue_after_memory_lock(
        job_type="memory_consolidate",
        retry_payload={
            "user_id": payload["user_id"],
            "lock_retries": payload.get("lock_retries") or 0,
        },
        dedupe_stem=f"memory_consolidate:{payload['user_id']}",
        warning=(
            f"Memory consolidation dropped after lock retries user_id={payload.get('user_id')}"
        ),
    )


async def _handle_todos(settings: Settings, payload: dict[str, Any]) -> None:
    await todo_sync.sync_todos_from_chat(
        settings,
        user_id=UUID(payload["user_id"]),
        chat_id=UUID(payload["chat_id"]),
        transcript=payload["transcript"],
    )


async def _handle_projects(settings: Settings, payload: dict[str, Any]) -> None:
    await project_sync.sync_projects_from_chat(
        settings,
        user_id=UUID(payload["user_id"]),
        chat_id=UUID(payload["chat_id"]),
        transcript=payload["transcript"],
    )


async def _handle_compress(settings: Settings, payload: dict[str, Any]) -> None:
    user_id_raw = payload.get("user_id")
    user_id = UUID(user_id_raw) if user_id_raw else None
    await compaction.compress_chat_history(settings, UUID(payload["chat_id"]), user_id=user_id)


async def _handle_suggestions(settings: Settings, payload: dict[str, Any]) -> None:
    await suggestion_generation.generate_suggestions(
        settings,
        UUID(payload["user_id"]),
    )


async def _handle_gmail_sync(settings: Settings, payload: dict[str, Any]) -> None:
    async with SessionLocal() as session:
        await gmail_sync.sync_gmail_for_user(
            session,
            settings,
            user_id=UUID(payload["user_id"]),
        )


async def _handle_transactional_email(settings: Settings, payload: dict[str, Any]) -> None:
    """Best-effort outbound email (welcome / receipts). Never raises into chat."""
    from app.repositories import users as users_repo

    async with SessionLocal() as session:
        user = await users_repo.get_by_id(session, UUID(payload["user_id"]))
    if user is None:
        logger.warning("transactional_email: user not found id=%s", payload.get("user_id"))
        return
    kind = payload.get("kind")
    try:
        if kind == "welcome":
            await transactional_email_service.send_welcome(settings, user)
        elif kind == "receipt":
            await transactional_email_service.send_purchase_receipt(
                settings,
                user,
                event_type=str(payload.get("event_type") or ""),
                store=payload.get("store"),
                product_id=payload.get("product_id"),
                expiration=payload.get("expiration"),
            )
        else:
            logger.warning("transactional_email: unknown kind=%s", kind)
    except Exception:
        logger.exception(
            "transactional_email job failed kind=%s user=%s", kind, payload.get("user_id")
        )


def register_all() -> None:
    """Register every live job type. Idempotent — `register` overwrites by key."""
    register("topic", _handle_topic)
    register("memory", _handle_memory)
    register("memory_consolidate", _handle_memory_consolidate)
    register("todos", _handle_todos)
    register("projects", _handle_projects)
    register("compress", _handle_compress)
    register("suggestions", _handle_suggestions)
    register("gmail_sync", _handle_gmail_sync)
    register("transactional_email", _handle_transactional_email)
    register("attachment_index", attachment_indexing.index_attachment_job)


register_all()
