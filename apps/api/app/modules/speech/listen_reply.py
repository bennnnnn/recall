"""The language a reply's lead clip was played in, kept for the rest of that reply.

The phone sends a reply to Listen in clips (``tts_followup``): a lead, then rest clips that
name the lead's hash. Each rest clip follows the lead's language (``clip_language``), so a
clip of numbers or a name does not switch the reply to another voice. Best effort: without
the record a clip is read by its own language.
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis

from app.modules.speech.text_language import UNSURE

logger = logging.getLogger(__name__)

# A long reply plays for a few minutes; each rest clip renews the record.
_TTL_SECONDS = 600


def _key(user_id: object, lead_hash: str) -> str:
    return f"speech_tts_language:{user_id}:{lead_hash}"


async def remember_reply_language(
    redis: Redis, user_id: object, lead_hash: str, language: str | None
) -> None:
    """After a lead clip: the language it was read as (``UNSURE`` for none)."""
    try:
        await redis.set(_key(user_id, lead_hash), language or UNSURE, ex=_TTL_SECONDS)
    except Exception:
        logger.warning("Listen could not keep a reply's language", exc_info=True)


async def reply_language(redis: Redis, user_id: object, lead_hash: str) -> str | None:
    """The language the reply's lead was read as, ``UNSURE``, or None with no record."""
    if not lead_hash:
        return None
    key = _key(user_id, lead_hash)
    try:
        raw = await redis.get(key)
        if raw is None:
            return None
        await redis.expire(key, _TTL_SECONDS)
    except Exception:
        logger.warning("Listen could not read a reply's language", exc_info=True)
        return None
    return raw.decode() if isinstance(raw, bytes | bytearray) else str(raw)
