"""Per-user cache generations in Redis.

A cache key that folds in the user's current generation goes unreachable the
moment the generation changes, so invalidation needs no SCAN. The generation
used to be an INCR counter with no TTL: one key per user, kept forever, even
after the account was deleted.

Now each bump stores a fresh random value with a TTL. Random rather than
INCR, so a key that expired and starts over can never land on a generation an
older cache entry was written under. The TTL only has to outlast the caches
that fold it in (minutes); a reader that finds no key uses generation "0",
which was last current before the first bump, at least a TTL ago.
"""

from __future__ import annotations

import secrets

from redis.asyncio import Redis

GENERATION_TTL_SECONDS = 30 * 24 * 60 * 60


async def bump_generation(redis: Redis, key: str) -> None:
    await redis.set(key, secrets.token_hex(8), ex=GENERATION_TTL_SECONDS)
