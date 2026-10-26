"""A deleted account's limits are filed under its email only when its provider owns it.

The email key (``quota_carryover``) let a quota be handed to a stranger: a Google account
can be verified on an address Google does not own (a stale work address, a lapsed domain,
``email_authority``). Its holder signs up with it, uses up the day and the live talk month,
deletes the account, and whoever signs up on that address next started at those counts.
Account delete now files the email key only when one of the account's sign-in providers
owns the address on ``email_authority``'s rules, read from the account row: Google for
Gmail, Apple for iCloud, me.com, mac.com and its relay. A Workspace address (owned through
the token's ``hd``, which the row does not keep) cannot be decided at delete, so it gets no
email key. The identity keys are unchanged.

Real Postgres and the configured Redis (``real_redis``), through the HTTP sign-in and
delete routes.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.models.orm import User
from app.modules.account import quota_carryover
from app.services import quota

from .carry_world import Linked, counts, delete, deleted_account, signed_in, use

_DELETED = {"usage": 1234, "imggen": 2, "tavily": 4}
_LIVE_TALK_SECONDS = 300


def _address(domain: str) -> str:
    return f"owner-{uuid4().hex[:12]}@{domain}"


def _email_key(world: Linked, email: str) -> str:
    key = quota_carryover.email_carry_key(world.settings, email)
    assert key is not None
    return key


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("deleted", "domain", "claims", "later"),
    [
        # A Google account verified on an iCloud address: Apple owns it, Google does not.
        ("google", "icloud.com", {}, "apple"),
        # A Google account on a company domain that is not its Workspace (no ``hd``).
        ("google", "example.org", {}, "google"),
        # An Apple ID whose shared address is a Gmail one: Google owns it, Apple does not.
        ("apple", "gmail.com", {}, "google"),
        # Google owns a Workspace address through the token's ``hd``, which the account
        # row does not keep: the delete cannot tell, so it keeps no email key.
        ("google", "acme-carry.example", {"hd": "acme-carry.example"}, "apple"),
    ],
)
async def test_quota_carryover_email_unowned_address_starts_the_next_sign_up_fresh(
    linked: Linked, deleted: str, domain: str, claims: dict[str, Any], later: str
) -> None:
    """Delete an account whose provider does not own (or cannot be shown at delete to own)
    its address: only the identity key is kept, and a later sign-up on that address with
    another login starts from zero. Before, it started at the deleted account's counts."""
    email = _address(domain)
    deleted_sub = await deleted_account(
        linked, deleted, email, _DELETED, live_talk=_LIVE_TALK_SECONDS, claims=claims
    )
    assert await linked.redis.get(_email_key(linked, email)) is None
    identity_key = quota_carryover.carry_key(linked.settings, deleted, deleted_sub)
    assert await linked.redis.get(identity_key) is not None

    fresh, _ = await signed_in(linked, later, f"{later}-{uuid4()}", email)
    assert await counts(linked.redis, fresh) == {}
    assert await quota.live_talk_used_seconds(linked.redis, fresh) == 0
    # The deleted login itself still carries its own day (its identity key is unchanged).
    again, _ = await signed_in(linked, deleted, deleted_sub, _address("gmail.com"), claims)
    assert await counts(linked.redis, again) == _DELETED


@pytest.mark.asyncio
@pytest.mark.parametrize(("deleted", "domain"), [("google", "gmail.com"), ("apple", "icloud.com")])
async def test_quota_carryover_email_owned_address_carries_to_a_new_login(
    linked: Linked, deleted: str, domain: str
) -> None:
    """Deleted on an address its provider owns, the account files the email key, and a
    new login on that address (not the deleted one) starts at its counts."""
    email = _address(domain)
    await deleted_account(linked, deleted, email, _DELETED, live_talk=_LIVE_TALK_SECONDS)
    email_key = _email_key(linked, email)
    assert await linked.redis.get(email_key) is not None

    later = "apple" if deleted == "google" else "google"
    fresh, _ = await signed_in(linked, later, f"{later}-{uuid4()}", email)
    assert await counts(linked.redis, fresh) == _DELETED
    assert await quota.live_talk_used_seconds(linked.redis, fresh) == _LIVE_TALK_SECONDS
    assert await linked.redis.get(email_key) is None


@pytest.mark.asyncio
async def test_quota_carryover_email_both_logins_store_it_when_either_owns(
    linked: Linked,
) -> None:
    """A Google account on an iCloud address that Apple then joins (Apple owns iCloud)
    holds both logins; Apple owning the address is enough to file the email key."""
    email = _address("icloud.com")
    user_id, _ = await signed_in(linked, "google", f"google-{uuid4()}", email)
    joined, token = await signed_in(linked, "apple", f"apple-{uuid4()}", email)
    assert joined == user_id
    await use(linked.redis, user_id, _DELETED, live_talk=_LIVE_TALK_SECONDS)
    await delete(linked, user_id, token)
    assert await linked.redis.get(_email_key(linked, email)) is not None

    fresh, _ = await signed_in(linked, "apple", f"apple-{uuid4()}", email)
    assert await counts(linked.redis, fresh) == _DELETED


@pytest.mark.asyncio
async def test_quota_carryover_email_both_logins_on_a_workspace_address_store_none(
    linked: Linked,
) -> None:
    """An Apple account on a company address that a Workspace Google login (``hd``) then
    joins: Google owned it at that sign-in, but the delete has no token to tell, and Apple
    never owns it, so no email key is filed."""
    domain = "acme-both.example"
    email = _address(domain)
    user_id, _ = await signed_in(linked, "apple", f"apple-{uuid4()}", email)
    joined, token = await signed_in(linked, "google", f"google-{uuid4()}", email, {"hd": domain})
    assert joined == user_id
    await use(linked.redis, user_id, _DELETED)
    await delete(linked, user_id, token)
    assert await linked.redis.get(_email_key(linked, email)) is None


@pytest.mark.parametrize(
    ("google_sub", "apple_sub", "email", "owned"),
    [
        ("g", None, "x@gmail.com", True),
        ("g", None, " X@GoogleMail.COM ", True),
        ("g", None, "x@icloud.com", False),
        ("g", None, "x@acme.example", False),
        (None, "a", "x@icloud.com", True),
        (None, "a", "x@me.com", True),
        (None, "a", "x@mac.com", True),
        (None, "a", "abc@privaterelay.appleid.com", True),
        (None, "a", "x@gmail.com", False),
        ("g", "a", "x@icloud.com", True),
        ("g", "a", "x@gmail.com", True),
        ("g", "a", "x@acme.example", False),
        (None, None, "x@gmail.com", False),
        ("g", "a", "", False),
        ("g", None, "not-an-address", False),
    ],
)
def test_quota_carryover_email_owned_by_sign_in(
    google_sub: str | None, apple_sub: str | None, email: str, owned: bool
) -> None:
    user = User(google_sub=google_sub, apple_sub=apple_sub, email=email)
    assert quota_carryover.email_owned_by_sign_in(user) is owned
