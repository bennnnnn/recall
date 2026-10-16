import logging
import math
from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import BaseModel, NonNegativeInt
from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

from app.core.config import Settings
from app.exceptions import RedisUnavailableError
from app.models.orm import User
from app.modules.billing.entitlements import allowance, is_paid

logger = logging.getLogger(__name__)

# Plan names are the app's to show (i18n); server copy says "upgrade", never a
# plan name, and never a number that config owns.
# Shown when the daily quota is exhausted — avoid internal "token" wording.
# Counters reset at midnight UTC (not the user's local timezone).
QUOTA_EXCEEDED_MESSAGE_FREE = (
    "You've used up today's free limit. Upgrade for more — or try again after midnight UTC."
)
QUOTA_EXCEEDED_MESSAGE_PAID = "You've reached today's limit. Try again after midnight UTC."

IMAGE_LIMIT_EXCEEDED_MESSAGE_FREE = (
    "You've reached today's image upload limit. Upgrade for more — or try again after midnight UTC."
)
IMAGE_LIMIT_EXCEEDED_MESSAGE_PAID = (
    "You've reached today's image upload limit. Try again after midnight UTC."
)

SPEECH_LIMIT_EXCEEDED_MESSAGE = (
    "You've reached today's voice transcription limit. Try again after midnight UTC."
)
SPEECH_NOT_IN_PLAN_MESSAGE = "Voice input isn't part of your plan. Upgrade to dictate messages."
SPEECH_RATE_LIMIT_MESSAGE = "Too many voice requests. Please wait a moment and try again."
SPEECH_TTS_RATE_LIMIT_MESSAGE = "Too many read-aloud requests. Please wait a moment and try again."
SPEECH_TTS_LIMIT_EXCEEDED_MESSAGE = "Daily read-aloud limit reached. Try again tomorrow."
SPEECH_TTS_NOT_IN_PLAN_MESSAGE = (
    "Read aloud isn't part of your plan. Upgrade for it, or use your phone's voice."
)

IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_FREE = (
    "You've reached today's image generation limit. "
    "Upgrade for more — or try again after midnight UTC."
)
IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_PAID = (
    "You've reached today's image generation limit. Try again after midnight UTC."
)
IMAGE_GENERATION_NOT_IN_PLAN_MESSAGE = "Image generation isn't part of your plan. Upgrade for it."
IMAGE_GENERATION_SPEND_CAP_MESSAGE = "Image generation is temporarily unavailable. Try again later."

IMAGE_SEARCH_LIMIT_EXCEEDED_MESSAGE_FREE = (
    "You've reached today's photo lookup limit. Upgrade for more — or try again after midnight UTC."
)
IMAGE_SEARCH_LIMIT_EXCEEDED_MESSAGE_PAID = (
    "You've reached today's photo lookup limit. Try again after midnight UTC."
)
IMAGE_SEARCH_SPEND_CAP_MESSAGE = "Photo lookup is temporarily unavailable. Try again later."

LIVE_TALK_NOT_IN_PLAN_MESSAGE = (
    "Live talk isn't part of your plan. Upgrade to talk with Recall out loud."
)
LIVE_TALK_MINUTES_USED_MESSAGE = (
    "You've used this month's live talk minutes. They renew on the 1st (UTC)."
)
LIVE_TALK_RATE_LIMIT_MESSAGE = "Too many live talk requests. Please wait a moment and try again."


def _plan_message(user: User, *, free: str, paid: str) -> str:
    return paid if is_paid(user) else free


def quota_exceeded_message(user: User) -> str:
    return _plan_message(user, free=QUOTA_EXCEEDED_MESSAGE_FREE, paid=QUOTA_EXCEEDED_MESSAGE_PAID)


def image_limit_exceeded_message(user: User) -> str:
    return _plan_message(
        user,
        free=IMAGE_LIMIT_EXCEEDED_MESSAGE_FREE,
        paid=IMAGE_LIMIT_EXCEEDED_MESSAGE_PAID,
    )


def speech_limit_exceeded_message(user: User) -> str:
    return SPEECH_LIMIT_EXCEEDED_MESSAGE


def image_generation_limit_exceeded_message(user: User) -> str:
    return _plan_message(
        user,
        free=IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_FREE,
        paid=IMAGE_GENERATION_LIMIT_EXCEEDED_MESSAGE_PAID,
    )


def image_search_limit_exceeded_message(user: User) -> str:
    return _plan_message(
        user,
        free=IMAGE_SEARCH_LIMIT_EXCEEDED_MESSAGE_FREE,
        paid=IMAGE_SEARCH_LIMIT_EXCEEDED_MESSAGE_PAID,
    )


def speech_tts_limit_exceeded_message(user: User) -> str:
    return SPEECH_TTS_LIMIT_EXCEEDED_MESSAGE


def utc_today() -> date:
    return datetime.now(UTC).date()


def _daily_key(prefix: str, owner: str | UUID, day: date | None = None) -> str:
    """Per-user, per-UTC-day counter key shared by every daily cap."""
    return f"{prefix}:{owner}:{(day or utc_today()).isoformat()}"


# Every per-user daily cap's counter prefix. Account delete carries today's
# values to a new account for the same sign-in (``read_carried_usage``), so a
# new daily cap is listed here too (a test checks every ``_daily_key`` use).
DAILY_COUNTER_PREFIXES: tuple[str, ...] = (
    "usage",
    "imgup",
    "speech",
    "tts",
    "tavily",
    "imggen",
    "imgsearch",
)


def _usage_key(user_id: str, day: date) -> str:
    return _daily_key("usage", user_id, day)


def _heal_flag_key(user_id: str, day: date) -> str:
    return _daily_key("usage:heal", user_id, day)


# Daily counters outlive their day by enough to read yesterday, then expire.
_DAILY_TTL = 60 * 60 * 48

# Raise Redis to db_total only when missing or behind. Never lower a live counter.
_HEAL_USAGE_LUA = """
local db = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local cur = redis.call('GET', KEYS[1])
if not cur then
  redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ttl)
  return db
end
local n = tonumber(cur)
if n < db then
  redis.call('SET', KEYS[1], ARGV[1], 'EX', ttl)
  return db
end
return n
"""


# Floor the daily usage counter at 0 so a buggy double-refund can never drive it
# negative (which would grant the user free quota). Set on refund/record.
async def _floor_counter(redis: Redis, key: str) -> None:
    """Clamp a counter to 0 without wiping its TTL (SET alone drops EXPIRE)."""
    await redis.set(key, 0, keepttl=True)


async def _reserve_daily_slot(redis: Redis, key: str, *, limit: int) -> bool:
    """Atomically take one slot from a per-day cap; roll back when over limit.

    INCR-then-rollback keeps parallel requests honest: the loser of a race
    lands over the limit and gives its slot back, so the cap can't be
    exceeded by concurrent calls. A limit of 0 (feature off / not entitled)
    always refuses.

    M10: Redis outages fail closed with ``RedisUnavailableError`` — same
    pattern as ``reserve_usage`` so speech/image/Tavily paths return 503
    instead of an opaque 500.
    """
    if limit <= 0:
        return False
    try:
        new_total = await redis.incrby(key, 1)
        if new_total == 1:
            await redis.expire(key, _DAILY_TTL)
        if new_total > limit:
            await redis.incrby(key, -1)
            return False
        return True
    except RedisError as exc:
        logger.warning("Daily slot reserve failed; Redis unavailable key=%s", key, exc_info=True)
        raise RedisUnavailableError() from exc


async def _refund_daily(redis: Redis, key: str, *, amount: int = 1) -> None:
    """Give back reserved units, flooring at zero (double-refund safe)."""
    new_total = await redis.incrby(key, -amount)
    if new_total < 0:
        await _floor_counter(redis, key)


def daily_limit_for_user(user: User, settings: Settings) -> int:
    return allowance(user, "daily_tokens", settings)


async def get_daily_usage(redis: Redis, user_id: str) -> int:
    key = _usage_key(user_id, utc_today())
    value = await redis.get(key)
    return int(value or 0)


async def has_daily_usage_key(redis: Redis, user_id: str, *, day: date | None = None) -> bool:
    """True when today's Redis usage counter already exists (seed is a no-op)."""
    return bool(await redis.exists(_usage_key(user_id, day or utc_today())))


async def seed_usage_if_missing(
    redis: Redis,
    user_id: str,
    db_total: int,
    *,
    day: date | None = None,
) -> None:
    """Self-heal the Redis daily counter after a flush/eviction.

    If the Redis key for today is absent, seed it with the DB-recorded total so
    quota enforcement resumes from the correct baseline instead of resetting to
    zero. Uses SET NX so concurrent calls (e.g. overlapping turns) can't
    double-count, and never overwrites a live counter. No-op when db_total <= 0.
    """
    if db_total <= 0:
        return
    key = _usage_key(user_id, day or utc_today())
    await redis.set(key, db_total, nx=True, ex=_DAILY_TTL)


async def mark_usage_needs_heal(
    redis: Redis,
    user_id: str,
    *,
    day: date | None = None,
) -> None:
    """Remember that post-commit ``adjust_usage`` failed so the next turn can heal."""
    try:
        await redis.set(_heal_flag_key(user_id, day or utc_today()), "1", ex=_DAILY_TTL)
    except RedisError:
        logger.warning("mark_usage_needs_heal failed user_id=%s", user_id, exc_info=True)


async def usage_needs_heal(
    redis: Redis,
    user_id: str,
    *,
    day: date | None = None,
) -> bool:
    try:
        return bool(await redis.exists(_heal_flag_key(user_id, day or utc_today())))
    except RedisError:
        logger.warning("usage_needs_heal failed user_id=%s", user_id, exc_info=True)
        return False


async def clear_usage_needs_heal(
    redis: Redis,
    user_id: str,
    *,
    day: date | None = None,
) -> None:
    try:
        await redis.delete(_heal_flag_key(user_id, day or utc_today()))
    except RedisError:
        logger.warning("clear_usage_needs_heal failed user_id=%s", user_id, exc_info=True)


async def _raise_counter_cas(redis: Redis, key: str, floor: int, ttl: int) -> None:
    current = await redis.get(key)
    if current is None:
        await redis.set(key, floor, nx=True, ex=ttl)
        return
    if int(current) < floor:
        await redis.set(key, floor, ex=ttl)


async def _raise_counter(redis: Redis, key: str, floor: int, *, ttl: int) -> None:
    """Raise a counter to *floor* when missing or behind; never lower it.

    Atomic via Lua; GET+SET fallback when EVAL is unavailable (some fakeredis
    setups).
    """
    try:
        await redis.eval(_HEAL_USAGE_LUA, 1, key, str(floor), str(ttl))
    except ResponseError:
        await _raise_counter_cas(redis, key, floor, ttl)


async def heal_usage_drift(
    redis: Redis,
    user_id: str,
    db_total: int,
    *,
    day: date | None = None,
) -> None:
    """Heal Redis/DB drift when Redis holds a stale value lower than the DB.

    ``seed_usage_if_missing`` only seeds when the key is absent — if Redis
    holds a stale value *lower* than the DB total (repeated ``adjust_usage``
    failures, partial outages, manual key edits), seeding is skipped forever
    for that UTC day and the user can exceed daily limits. This compares the
    two and raises Redis to ``max(redis, db_total)`` when DB is ahead. Never
    lowers a live counter. Atomic via Lua; GET+SET fallback when EVAL is
    unavailable (some fakeredis setups).
    """
    if db_total <= 0:
        return
    key = _usage_key(user_id, day or utc_today())
    try:
        await _raise_counter(redis, key, db_total, ttl=_DAILY_TTL)
    except RedisError:
        logger.warning("heal_usage_drift failed user_id=%s", user_id, exc_info=True)
        raise


async def reserve_usage(
    redis: Redis,
    user_id: str,
    requested: int,
    *,
    daily_limit: int,
) -> bool:
    """Atomically reserve tokens before generation. Refunds if over limit.

    Redis outages fail closed (``RedisUnavailableError``) — never skip the
    reserve and allow unbounded generation.
    """
    if requested <= 0:
        return True
    key = _usage_key(user_id, utc_today())
    try:
        new_total = await redis.incrby(key, requested)
        if new_total == requested:
            await redis.expire(key, _DAILY_TTL)
        if new_total > daily_limit:
            # Roll back the over-limit reservation. If this incrby fails
            # (Redis blip after the first succeeded), the user would be
            # permanently charged for a turn that was rejected — retry once
            # so the charge doesn't stick.
            try:
                await redis.incrby(key, -requested)
            except RedisError:
                logger.warning(
                    "Quota over-limit rollback failed; retrying user_id=%s", user_id, exc_info=True
                )
                await redis.incrby(key, -requested)
            return False
        return True
    except RedisError as exc:
        logger.warning("Quota reserve failed; Redis unavailable user_id=%s", user_id, exc_info=True)
        raise RedisUnavailableError() from exc


async def refund_usage(redis: Redis, user_id: str, amount: int) -> None:
    if amount <= 0:
        return
    await _refund_daily(redis, _usage_key(user_id, utc_today()), amount=amount)


async def adjust_usage(
    redis: Redis,
    user_id: str,
    reserved: int,
    actual: int,
    *,
    daily_limit: int | None = None,
) -> int:
    delta = actual - reserved
    if delta == 0:
        return await get_daily_usage(redis, user_id)
    return await record_usage(redis, user_id, delta, daily_limit=daily_limit)


async def record_usage(
    redis: Redis,
    user_id: str,
    tokens: int,
    *,
    daily_limit: int | None = None,
) -> int:
    key = _usage_key(user_id, utc_today())
    new_total = await redis.incrby(key, tokens)
    if new_total == tokens:
        await redis.expire(key, _DAILY_TTL)
    if new_total < 0:
        await _floor_counter(redis, key)
        new_total = 0
    # Cap overshoot: a single turn whose actual usage exceeds the reserve
    # estimate can push the daily counter past the limit. Clip at daily_limit
    # so one turn can't blow the cap (the over-limit tokens are forfeit —
    # they were genuinely used, but the counter must not exceed the limit
    # or subsequent reserve_usage checks under-report remaining quota).
    if daily_limit is not None and new_total > daily_limit:
        await redis.set(key, daily_limit, ex=_DAILY_TTL)
        new_total = daily_limit
    return new_total


async def remaining(redis: Redis, user_id: str, *, daily_limit: int) -> int:
    used = await get_daily_usage(redis, user_id)
    return max(0, daily_limit - used)


async def reset_daily_usage(redis: Redis, user_id: str, day: date | None = None) -> None:
    """Clear Redis quota counter for a user/day (dev support)."""
    await redis.delete(_usage_key(user_id, day or utc_today()))


# ── Daily image-upload cap (separate from the token quota) ───────────────────
# Vision/image inputs cost more than text and aren't well captured by the text
# token reserve, so image uploads are capped per user per UTC day. Counted at
# upload-completion time (when bytes are actually stored); checked at presign.


def image_upload_limit_for_user(user: User, settings: Settings) -> int:
    return allowance(user, "daily_image_uploads", settings)


async def get_image_upload_count(redis: Redis, user_id: UUID) -> int:
    value = await redis.get(_daily_key("imgup", user_id))
    return int(value or 0)


async def reserve_image_upload(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    """Atomically reserve one image upload slot for today. Rolls back if over limit."""
    return await _reserve_daily_slot(redis, _daily_key("imgup", user_id), limit=limit)


async def refund_image_upload(redis: Redis, user_id: UUID) -> None:
    """Release a reserved image slot (e.g. failed or cancelled upload). Floors at zero.

    Unlike the other refunds this never decrements below an absent/zero key —
    a refund without a matching reserve must not create a negative counter.
    """
    key = _daily_key("imgup", user_id)
    value = await redis.get(key)
    if not value:
        return
    if int(value) <= 0:
        return
    await redis.incrby(key, -1)


# ── Speech transcription caps ────────────────────────────────────────────────


def speech_transcription_limit_for_user(user: User, settings: Settings) -> int:
    return allowance(user, "daily_speech_transcriptions", settings)


async def reserve_speech_transcription(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    return await _reserve_daily_slot(redis, _daily_key("speech", user_id), limit=limit)


async def refund_speech_transcription(redis: Redis, user_id: UUID) -> None:
    await _refund_daily(redis, _daily_key("speech", user_id))


def speech_tts_limit_for_user(user: User, settings: Settings) -> int:
    return allowance(user, "daily_speech_tts", settings)


async def reserve_speech_tts(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    return await _reserve_daily_slot(redis, _daily_key("tts", user_id), limit=limit)


async def refund_speech_tts(redis: Redis, user_id: UUID) -> None:
    await _refund_daily(redis, _daily_key("tts", user_id))


# ── Tavily web-search caps (DDG fallback when exceeded) ────────────────────────


def tavily_search_limit_for_user(user: User, settings: Settings) -> int:
    return allowance(user, "daily_web_searches", settings)


async def reserve_tavily_search(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    return await _reserve_daily_slot(redis, _daily_key("tavily", user_id), limit=limit)


# ── AI image generation caps (per plan; 0 = not part of that plan) ──────────


def image_generation_limit_for_user(user: User, settings: Settings) -> int:
    return allowance(user, "daily_image_generations", settings)


async def reserve_image_generation(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    return await _reserve_daily_slot(redis, _daily_key("imggen", user_id), limit=limit)


async def refund_image_generation(redis: Redis, user_id: UUID) -> None:
    await _refund_daily(redis, _daily_key("imggen", user_id))


IMAGE_GEN_SPEND_USD = 0.03
WEB_SEARCH_CLASSIFIER_SPEND_USD = 0.001
REFERENCE_RESOLVER_SPEND_USD = 0.001
# Tavily image search + one SSRF-safe fetch (cheaper than image-gen, still billed).
IMAGE_SEARCH_SPEND_USD = 0.01
# One scan read-back: Mathpix, plus a vision call when the page needs it.
MATH_SCAN_READ_SPEND_USD = 0.005


# ── Reference-photo lookup caps (every plan, per-plan cap) ──────────────────


def image_search_limit_for_user(user: User, settings: Settings) -> int:
    return allowance(user, "daily_image_searches", settings)


async def reserve_image_search(redis: Redis, user_id: UUID, *, limit: int) -> bool:
    return await _reserve_daily_slot(redis, _daily_key("imgsearch", user_id), limit=limit)


async def refund_image_search(redis: Redis, user_id: UUID) -> None:
    await _refund_daily(redis, _daily_key("imgsearch", user_id))


# ── Live talk minutes (a monthly allowance per plan) ────────────────────────
# Live talk runs phone <-> OpenAI over WebRTC once the server mints a session,
# so the server meters time at its own boundary: mint reserves a capped
# session length out of this UTC month's seconds, and the end report settles
# it to the time that actually passed (never refunding past the reservation).
# A phone that never reports keeps the full reservation charged.

VOICE_SPEND_CAP_MESSAGE = "Voice is temporarily unavailable. Try again later."
STT_SPEND_USD = 0.01
TTS_SPEND_USD = 0.015
LIVE_TALK_SESSION_SPEND_USD = 0.03
LIVE_TALK_TURN_SPEND_USD = 0.08
# A month counter outlives its month long enough for a late settle, then expires.
_MONTHLY_TTL = 60 * 60 * 24 * 40
# A reservation waits this long past its session for the phone's end report.
_LIVE_TALK_SETTLE_GRACE_SECONDS = 15 * 60


def utc_month(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m")


def next_month_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    if current.month == 12:
        return datetime(current.year + 1, 1, 1, tzinfo=UTC)
    return datetime(current.year, current.month + 1, 1, tzinfo=UTC)


def _live_talk_month_key(user_id: UUID, month: str) -> str:
    return f"livetalk_sec:{user_id}:{month}"


def _live_talk_reservation_key(user_id: UUID, session_id: str) -> str:
    return f"livetalk_res:{user_id}:{session_id}"


def live_talk_allowance_seconds(user: User, settings: Settings) -> int:
    return allowance(user, "monthly_live_talk_minutes", settings) * 60


async def live_talk_used_seconds(redis: Redis, user_id: UUID, *, month: str | None = None) -> int:
    value = await redis.get(_live_talk_month_key(user_id, month or utc_month()))
    return max(0, int(value or 0))


async def reserve_live_talk_seconds(
    redis: Redis,
    user_id: UUID,
    *,
    allowance_seconds: int,
    max_session_seconds: int,
    min_session_seconds: int,
) -> int:
    """Take up to one session's seconds from this month. 0 = refused.

    INCRBY-then-trim keeps parallel mints honest: whoever lands past the
    allowance gives the excess back, and drops out entirely when what is left
    for it is under the minimum session.
    """
    if allowance_seconds <= 0 or max_session_seconds <= 0:
        return 0
    floor = max(1, min_session_seconds)
    key = _live_talk_month_key(user_id, utc_month())
    try:
        used = int(await redis.get(key) or 0)
        grant = min(max_session_seconds, allowance_seconds - used)
        if grant < floor:
            return 0
        total = await redis.incrby(key, grant)
        if total == grant:
            await redis.expire(key, _MONTHLY_TTL)
        overshoot = total - allowance_seconds
        if overshoot > 0:
            if grant - overshoot < floor:
                await redis.incrby(key, -grant)
                return 0
            await redis.incrby(key, -overshoot)
            grant -= overshoot
        return grant
    except RedisError as exc:
        logger.warning(
            "Live talk reserve failed; Redis unavailable user=%s", user_id, exc_info=True
        )
        raise RedisUnavailableError() from exc


async def record_live_talk_reservation(
    redis: Redis, user_id: UUID, session_id: str, *, reserved_seconds: int
) -> None:
    started_ms = int(datetime.now(UTC).timestamp() * 1000)
    await redis.set(
        _live_talk_reservation_key(user_id, session_id),
        f"{reserved_seconds}:{started_ms}:{utc_month()}",
        ex=reserved_seconds + _LIVE_TALK_SETTLE_GRACE_SECONDS,
    )


async def release_live_talk_seconds(
    redis: Redis, user_id: UUID, *, seconds: int, month: str | None = None
) -> None:
    """Give back seconds that were reserved but never became a session."""
    if seconds <= 0:
        return
    await _refund_daily(redis, _live_talk_month_key(user_id, month or utc_month()), amount=seconds)


async def settle_live_talk_session(redis: Redis, user_id: UUID, session_id: str) -> int | None:
    """Charge the time that passed since mint; refund the rest of the reservation.

    Returns the seconds charged, or None when there is nothing to settle (an
    unknown session, a second report, or one that came after the grace window,
    which keeps the full reservation). The server's clock decides: a phone
    cannot shorten its own session by reporting less.
    """
    raw = await redis.getdel(_live_talk_reservation_key(user_id, (session_id or "").strip()))
    if raw is None:
        return None
    text = raw.decode() if isinstance(raw, bytes | bytearray) else str(raw)
    try:
        reserved_text, started_text, month = text.split(":", 2)
        reserved = int(reserved_text)
        started_ms = int(started_text)
    except ValueError:
        return None
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    elapsed = math.ceil(max(0, now_ms - started_ms) / 1000)
    charged = min(reserved, elapsed)
    await release_live_talk_seconds(redis, user_id, seconds=reserved - charged, month=month)
    return charged


# ── Carry-over to a new account for the same sign-in ────────────────────────
# Counters are keyed by user id, so deleting an account and signing up again
# with the same Google/Apple login would start every cap from zero. Account
# delete reads today's counters and this month's live talk seconds; the new
# account's counters are raised to them (modules/account/quota_carryover.py).


class CarriedUsage(BaseModel):
    """One account's used counters for one UTC day (and its month)."""

    day: str
    month: str
    daily: dict[str, NonNegativeInt] = {}
    live_talk_seconds: NonNegativeInt = 0

    def is_empty(self) -> bool:
        return not any(self.daily.values()) and self.live_talk_seconds <= 0


def _counter_value(raw: object) -> int:
    try:
        return max(0, int(str(raw))) if raw is not None else 0
    except ValueError:
        return 0


async def read_carried_usage(redis: Redis, user_id: UUID) -> CarriedUsage:
    """Today's daily counters and this month's live talk seconds for *user_id*."""
    day = utc_today()
    month = utc_month()
    keys = [_daily_key(prefix, user_id, day) for prefix in DAILY_COUNTER_PREFIXES]
    keys.append(_live_talk_month_key(user_id, month))
    values = [_counter_value(raw) for raw in await redis.mget(keys)]
    daily = {
        prefix: used
        for prefix, used in zip(DAILY_COUNTER_PREFIXES, values[:-1], strict=True)
        if used > 0
    }
    return CarriedUsage(day=day.isoformat(), month=month, daily=daily, live_talk_seconds=values[-1])


async def apply_carried_usage(redis: Redis, user_id: UUID, carried: CarriedUsage) -> None:
    """Raise *user_id*'s counters to what was carried: max(existing, carried).

    Daily counters only on the same UTC day, live talk only in the same month;
    anything older has already reset. Raise-only, like the DB usage heal, so
    neither can lower the other.
    """
    day = utc_today()
    if carried.day == day.isoformat():
        for prefix, used in carried.daily.items():
            if prefix in DAILY_COUNTER_PREFIXES and used > 0:
                await _raise_counter(redis, _daily_key(prefix, user_id, day), used, ttl=_DAILY_TTL)
    month = utc_month()
    if carried.month == month and carried.live_talk_seconds > 0:
        await _raise_counter(
            redis,
            _live_talk_month_key(user_id, month),
            carried.live_talk_seconds,
            ttl=_MONTHLY_TTL,
        )


# ── Global UTC-day spend kill-switch (OpenRouter $) ──────────────────────────
# Integer micro-dollars (1e-6 USD) so INCRBY stays atomic, rounded UP so no
# paid call ever records as free. The previous unit was 1e-3 USD with
# round(): a typical $0.0002-0.0005 free-chat turn recorded 0, and the cap
# never saw free-tier traffic. 0-limit settings are unlimited (dev/tests).
# Redis errors fail closed: treat as exceeded so we do not burn money while
# the meter is blind.

_MICRO_USD_PER_USD = 1_000_000
# Pre-fix counter (1e-3 USD units). Still read so a mid-day deploy keeps the
# day's total; it expires with _DAILY_TTL and can be dropped after that.
_LEGACY_SPEND_UNITS_TO_MICRO_USD = 1_000


def _spend_key(day: date | None = None) -> str:
    return f"spend_musd:{(day or utc_today()).isoformat()}"


def _legacy_spend_key(day: date | None = None) -> str:
    return f"spend_mcents:{(day or utc_today()).isoformat()}"


def _usd_to_micro_usd(usd: float) -> int:
    if usd <= 0:
        return 0
    # round() first strips float noise (0.0004 * 1e6 = 400.00000000000006).
    return max(1, math.ceil(round(usd * _MICRO_USD_PER_USD, 6)))


async def record_global_spend(redis: Redis, usd: float) -> int:
    """Add estimated dollars to today's global spend counter. Returns micro-USD."""
    amount = _usd_to_micro_usd(usd)
    if amount <= 0:
        return await get_global_spend_micro_usd(redis)
    key = _spend_key()
    new_total = await redis.incrby(key, amount)
    if new_total == amount:
        await redis.expire(key, _DAILY_TTL)
    return new_total


async def get_global_spend_micro_usd(redis: Redis) -> int:
    value = await redis.get(_spend_key())
    legacy = await redis.get(_legacy_spend_key())
    return int(value or 0) + int(legacy or 0) * _LEGACY_SPEND_UNITS_TO_MICRO_USD


async def global_spend_exceeded(redis: Redis, settings: Settings) -> bool:
    """True when today's spend is at/over the cap, or Redis is down and a cap is set."""
    if settings.daily_global_spend_usd <= 0:
        return False
    limit = _usd_to_micro_usd(settings.daily_global_spend_usd)
    try:
        return await get_global_spend_micro_usd(redis) >= limit
    except RedisError:
        logger.warning("Global spend check failed; treating as exceeded", exc_info=True)
        return True


async def record_voice_spend(redis: Redis, usd: float) -> None:
    """Best-effort: voice cost must not fail the user path if Redis is unhappy."""
    try:
        await record_global_spend(redis, usd)
    except Exception:
        logger.exception("record_voice_spend failed")
