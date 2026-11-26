"""How many open to-dos one account may keep, and how many reminders it gets in one cycle.

Nothing capped either (security review, 2026-11-25): one account could keep 10,000
reminders due the same minute, and the push and email cycles, which drain one queue in
due order, sent every one of them before anyone else's, burning the email quota on the
way. The cap is far past any real list; the share keeps one account from filling a cycle.
"""

from __future__ import annotations

from collections import Counter
from uuid import UUID

from sqlalchemy import false, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainError
from app.models.orm import TodoItem

# Open (not completed) to-dos one account may keep. Adding one past it, or reopening a
# completed one, is refused 409 ``todo_limit``; the phone says so in the user's language.
OPEN_TODOS_MAX = 1000

# Reminders one account is sent by one channel in one cycle (a minute). The rest of its
# due reminders go in the cycles that follow, after everyone else's that are due.
REMINDERS_PER_ACCOUNT_PER_CYCLE = 20


# What live talk says when a reminder the user spoke meets the cap (English: other
# languages never write to-dos there).
TODO_LIST_FULL_REPLY = (
    f"I couldn't save that reminder: your to-do list has {OPEN_TODOS_MAX} open to-dos, the "
    "most Recall keeps. Complete or delete some, then ask again."
)


class TodoLimitError(DomainError):
    """The account has as many open to-dos as Recall keeps."""

    status_code = 409
    default_code = "todo_limit"


async def ensure_room_for_open(session: AsyncSession, user_id: UUID) -> None:
    """Refuse one more open to-do when the account already has ``OPEN_TODOS_MAX``.

    The account's adds take turns: a transaction-scoped advisory lock on the account is
    held from the count to the commit, so adds sent at once cannot all read 999.
    """
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(str(user_id)))))
    count = await session.scalar(
        select(func.count())
        .select_from(TodoItem)
        .where(TodoItem.user_id == user_id, TodoItem.checked == false())
    )
    if isinstance(count, int) and count >= OPEN_TODOS_MAX:
        raise TodoLimitError(
            f"You have {OPEN_TODOS_MAX} open to-dos, the most Recall keeps. "
            "Complete or delete some to add more."
        )


class AccountShare:
    """Each account's share of one reminder cycle: at most ``per_account`` sends each, so
    one account's backlog never holds back the reminders of everyone due after it. Only a
    send that will be tried takes from it: the channel asks after its held reminders are
    passed by, so a held one never stands in for a sendable one."""

    def __init__(self, per_account: int = REMINDERS_PER_ACCOUNT_PER_CYCLE) -> None:
        self._per_account = per_account
        self._taken: Counter[UUID] = Counter()

    def take(self, user_id: UUID) -> bool:
        """Whether the account may have one more reminder this cycle (and count it)."""
        if self._taken[user_id] >= self._per_account:
            return False
        self._taken[user_id] += 1
        return True
