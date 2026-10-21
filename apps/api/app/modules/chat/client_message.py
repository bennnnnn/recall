"""One turn per client message: a message the server already took never runs twice.

The phone names each message it sends (``client_message_id``) and keeps the name
on every later send of it: over a new socket after the old one went quiet, over
SSE, or from Retry. The first turn to claim the name runs. A later send is told
``duplicate`` (``stream_events.build_duplicate_event``) and the phone follows the
first turn by reloading the chat. A turn that ends with nothing saved gives the
name back, so a resend after a refusal (busy, quota) runs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from redis.asyncio import Redis

from app.modules.chat.turn_outcome import TurnOutcome

logger = logging.getLogger(__name__)

# Held this long while the turn runs: a machine that dies mid-turn frees it then.
CLAIM_RUNNING_TTL_SECONDS = 15 * 60
# Kept this long once the turn saved something: a resend or Retry within a day
# of it is recognized.
CLAIM_SAVED_TTL_SECONDS = 24 * 60 * 60


def claim_key(user_id: UUID, chat_id: UUID, client_message_id: UUID) -> str:
    return f"chat:client_msg:{user_id}:{chat_id}:{client_message_id}"


@dataclass(frozen=True)
class ClientMessageClaim:
    """A turn's hold on its message's name; ``settle`` it once the turn ended.

    A message sent without a name (older clients, web) has no hold to settle.
    """

    redis: Redis | None = None
    key: str | None = None

    async def settle(self, outcome: TurnOutcome) -> None:
        """Keep the name for a day when the turn saved its message or a reply; else free it."""
        if self.redis is None or self.key is None:
            return
        try:
            if outcome.user_message_saved or outcome.message_id is not None:
                await self.redis.expire(self.key, CLAIM_SAVED_TTL_SECONDS)
            else:
                await self.redis.delete(self.key)
        except Exception:
            # The running TTL frees it; a lost settle only delays a resend's turn.
            logger.warning("Client message claim not settled key=%s", self.key, exc_info=True)


UNNAMED = ClientMessageClaim()


async def claim_client_message(
    redis: Redis,
    *,
    user_id: UUID,
    chat_id: UUID,
    client_message_id: UUID | None,
) -> ClientMessageClaim | None:
    """This turn's claim on its message; None when an earlier turn already took it."""
    if client_message_id is None:
        return UNNAMED
    key = claim_key(user_id, chat_id, client_message_id)
    try:
        claimed = await redis.set(key, "1", nx=True, ex=CLAIM_RUNNING_TTL_SECONDS)
    except Exception:
        # Fail open, as the job dedupe does: the turn needs Redis for its lock
        # and quota anyway and reports an outage itself.
        logger.warning("Client message claim failed key=%s", key, exc_info=True)
        return UNNAMED
    return ClientMessageClaim(redis, key) if claimed else None
