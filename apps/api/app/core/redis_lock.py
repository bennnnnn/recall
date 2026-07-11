"""Token-based Redis locks for periodic schedulers.

``SET key token NX EX`` + Lua compare-and-delete so a slow cycle that outlives
its TTL cannot delete a lock owned by a later instance.
"""

from __future__ import annotations

import secrets
from typing import Final

from redis.asyncio import Redis

_RELEASE_LUA: Final[str] = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


async def acquire_lock(redis: Redis, key: str, ttl_seconds: int) -> str | None:
    token = secrets.token_hex(16)
    acquired = await redis.set(key, token, nx=True, ex=ttl_seconds)
    return token if acquired else None


async def release_lock(redis: Redis, key: str, token: str) -> None:
    await redis.eval(_RELEASE_LUA, 1, key, token)
