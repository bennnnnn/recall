from contextlib import ExitStack
from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit
from app.modules.chat.prompt_builder import fetch_web_and_tools, inject_web_and_tools
from app.modules.chat.turn_deps import ChatTurnDeps, default_deps
from app.services.solving import VerifiedSolveBlock


class FakeSessionCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        return False


class Overlay:
    """A real module with a few attributes swapped, seen only through one ``ChatTurnDeps``."""

    def __init__(self, base: Any, **swapped: Any) -> None:
        self._base = base
        self.__dict__.update(swapped)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


def turn_deps(**fields: Any) -> ChatTurnDeps:
    """``default_deps()`` with fields swapped for fakes.

    A dict keeps the real module and swaps only the names it lists:
    ``turn_deps(quota={"refund_usage": refund})``.
    """
    base = default_deps()
    swapped: dict[str, Any] = {
        name: Overlay(getattr(base, name), **value) if isinstance(value, dict) else value
        for name, value in fields.items()
    }
    return replace(base, **swapped)


async def augment_web_and_tools(
    prompt_messages: list[dict[str, str]],
    user_content: str,
    settings: Settings,
    **fetch_kwargs: Any,
) -> tuple[list[dict[str, str]], list[WebSearchHit], VerifiedSolveBlock | None]:
    """Fetch the web and subject blocks, then inject them, as a turn's Phase B/C does."""
    fetched = await fetch_web_and_tools(
        user_content, settings, prompt_messages=prompt_messages, **fetch_kwargs
    )
    updated = await inject_web_and_tools(prompt_messages, fetched.web_block, fetched.subject_block)
    return updated, fetched.search_sources, fetched.verified


def stub_recent(n: int) -> list[MagicMock]:
    """n chronological rows so prior_count can come from list_recent, not COUNT."""
    rows: list[MagicMock] = []
    for i in range(n):
        row = MagicMock()
        row.id = uuid4()
        row.role = "user" if i % 2 == 0 else "assistant"
        row.content = f"m{i}"
        rows.append(row)
    return rows


def offline_session_patches():
    return (
        patch("app.modules.chat.prompt_builder.SessionLocal", FakeSessionCM),
        patch("app.modules.chat.prompt_context.SessionLocal", FakeSessionCM),
        patch("app.modules.chat.turn_prep.attachments.SessionLocal", FakeSessionCM),
        patch("app.modules.chat.turn_prep.augment.SessionLocal", FakeSessionCM),
        patch("app.modules.chat.turn_prep.context.SessionLocal", FakeSessionCM),
        patch("app.modules.chat.turn_prep.instant.SessionLocal", FakeSessionCM),
        patch("app.modules.chat.turn_prep.persist.SessionLocal", FakeSessionCM),
        patch("app.modules.chat.turn_prep.vision.SessionLocal", FakeSessionCM),
        patch("app.modules.chat.post_turn.SessionLocal", FakeSessionCM),
    )


def offline_deps(**fields: Any) -> ChatTurnDeps:
    """The turn's own sessions offline, as ``stream_offline_io`` keeps the rest."""
    return turn_deps(session_factory=FakeSessionCM, **fields)


@pytest.fixture
def stream_offline_io():
    with ExitStack() as stack:
        for patcher in offline_session_patches():
            stack.enter_context(patcher)
        stack.enter_context(patch("app.modules.chat.post_turn.seed_usage_from_db", AsyncMock()))
        stack.enter_context(patch("app.services.quota.refund_usage", AsyncMock()))
        stack.enter_context(
            patch("app.repositories.messages.list_recent", AsyncMock(return_value=[]))
        )
        stack.enter_context(
            patch("app.modules.chat.turn_load.wait_for_pending_finalize", AsyncMock())
        )
        stack.enter_context(
            patch("app.modules.web_search.is_short_letter_answer", return_value=False)
        )
        yield
