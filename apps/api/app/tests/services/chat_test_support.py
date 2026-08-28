from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest


class FakeSessionCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        return False


def offline_session_patches():
    return (
        patch("app.services.chat.stream.SessionLocal", FakeSessionCM),
        patch("app.services.chat.prompt_builder.SessionLocal", FakeSessionCM),
        patch("app.services.chat.turn_prep.attachments.SessionLocal", FakeSessionCM),
        patch("app.services.chat.turn_prep.context.SessionLocal", FakeSessionCM),
        patch("app.services.chat.turn_prep.integrations.SessionLocal", FakeSessionCM),
        patch("app.services.chat.turn_prep.prepare.SessionLocal", FakeSessionCM),
        patch("app.services.chat.post_turn.SessionLocal", FakeSessionCM),
    )


def quiz_message_repo_patches():
    return (
        patch(
            "app.services.chat.quiz_messages.get_last_quiz_assistant",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.chat.quiz_messages.count_quiz_letter_answers_since",
            AsyncMock(return_value=0),
        ),
    )


@pytest.fixture
def stream_offline_io():
    with ExitStack() as stack:
        for patcher in offline_session_patches():
            stack.enter_context(patcher)
        stack.enter_context(patch("app.services.chat.post_turn.seed_usage_from_db", AsyncMock()))
        stack.enter_context(patch("app.services.quota.refund_usage", AsyncMock()))
        stack.enter_context(
            patch("app.repositories.messages.list_recent", AsyncMock(return_value=[]))
        )
        stack.enter_context(
            patch("app.services.chat.stream.wait_for_pending_finalize", AsyncMock())
        )
        for patcher in quiz_message_repo_patches():
            stack.enter_context(patcher)
        stack.enter_context(
            patch("app.services.web_search.is_vocab_quiz_answer", return_value=False)
        )
        stack.enter_context(
            patch(
                "app.services.calendar.has_write_access",
                AsyncMock(return_value=False),
            )
        )
        yield
