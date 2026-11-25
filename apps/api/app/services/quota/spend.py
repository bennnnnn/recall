"""Global UTC-day spend kill-switch: what each call adds, and what the cap stops.

The counter itself is ``core/spend_counter.py``. Chat turns add catalog price
x tokens at finalize, and every other model call (memory, titles, follow-ups,
OCR, embeddings, classifiers) is priced by the gateway that makes it
(``gateways/llm_spend.py``). The prices below are for calls without a token
count: images, photo lookup, scan reads, voice and live talk.
"""

import logging
import math
from datetime import date

from redis.asyncio import Redis

from app.core.spend_counter import (
    MICRO_USD_PER_USD,
    get_global_spend_micro_usd,
    global_spend_exceeded,
    record_global_spend,
    spend_key,
)
from app.services.quota.counters import refund_daily

logger = logging.getLogger(__name__)

__all__ = [
    "IMAGE_GEN_SPEND_USD",
    "IMAGE_SEARCH_SPEND_USD",
    "LIVE_TALK_SPEND_USD_PER_MINUTE",
    "MATHPIX_READ_SPEND_USD",
    "STT_OPENAI_LARGE_SPEND_USD",
    "STT_OPENAI_SPEND_USD",
    "STT_WHISPER_SPEND_USD",
    "get_global_spend_micro_usd",
    "global_spend_exceeded",
    "live_talk_spend_usd",
    "record_global_spend",
    "record_voice_spend",
    "release_global_spend",
]

IMAGE_GEN_SPEND_USD = 0.03
# Tavily image search + one SSRF-safe fetch (cheaper than image-gen, still billed).
IMAGE_SEARCH_SPEND_USD = 0.01
# One photo's Mathpix call. A vision read of the page is priced by the
# gateway on top, so this stays the old all-in estimate (conservative).
MATHPIX_READ_SPEND_USD = 0.005
# One recorded clip, by the transcriber that took it (``speech.service``; a Whisper failure
# then asked of OpenAI adds both). The phone stops a take at 45 s; the server takes up to
# 5 MB, about 310 s of the phone's 128 kbps AAC, and each estimate covers that whole upload.
# Whisper Large V3 Turbo on OpenRouter bills per second, $0.0000111/s at its dearest host
# (OpenRouter picks it): 310 s is $0.0035.
STT_WHISPER_SPEND_USD = 0.004
# gpt-4o-mini-transcribe bills tokens ($3/M audio in, $5/M text out): an 11 s Amharic clip
# named in the prompt read 128 tokens and once wrote 118 Ethiopic ones, about $0.001 (Hindi
# about half that), so 310 s is about $0.028.
STT_OPENAI_SPEND_USD = 0.03
# gpt-4o-transcribe (Amharic) bills twice mini's rates ($6/M audio in, $10/M text out): an
# 11 s Amharic clip read 112 audio tokens and wrote 129 Ethiopic ones, about $0.002
# (2026-11-24), so 310 s of speech is about $0.055.
STT_OPENAI_LARGE_SPEND_USD = 0.06
# Listen (TTS) is priced per clip by its characters, at its model's catalog rate
# (``ChatModel.usd_per_m_chars``): ``modules/speech/service.synthesize_speech``.
# An upper estimate of one minute of gpt-realtime conversation: audio both
# ways plus the context each reply re-reads. Live talk is priced by time, not
# by saved turn: the phone posts the turns, so a count of them is the client's.
LIVE_TALK_SPEND_USD_PER_MINUTE = 0.20


async def release_global_spend(redis: Redis, usd: float, *, day: date) -> None:
    """Give back spend recorded on *day* that never happened, never below 0.

    Rounds down, so a release never exceeds what ``record_global_spend``
    rounded up.
    """
    amount = math.floor(round(usd * MICRO_USD_PER_USD, 6))
    if amount > 0:
        await refund_daily(redis, spend_key(day), amount=amount)


def live_talk_spend_usd(seconds: int) -> float:
    return max(0, seconds) * LIVE_TALK_SPEND_USD_PER_MINUTE / 60


async def record_voice_spend(redis: Redis, usd: float) -> None:
    """Best-effort: voice cost must not fail the user path if Redis is unhappy."""
    try:
        await record_global_spend(redis, usd)
    except Exception:
        logger.exception("record_voice_spend failed")
