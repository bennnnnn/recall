"""A regenerate reads its line against the reply before it, not the reply it redoes.

The regenerate's window still ends with the reply being replaced. Read against it, a
"yes" to the reply's question lost what it answered, and the redone reply was the live
bug again (2026-10-25). Here the question is a clarify card: the picks sent after it
are still read as its answer when the reply to them is redone.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import fakeredis.aioredis

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.models.orm import Chat, Message, User
from app.modules.chat.turn_deps import default_deps
from app.modules.chat.turn_load import load_regenerate_turn
from app.repositories import users as users_repo

_CARD = {
    "questions": [
        {
            "id": "region",
            "label": "Region",
            "question": "Which region are you considering?",
            "options": ["Anywhere", "Europe", "The Americas"],
        }
    ],
    "closing": "Compare the strongest options.",
    "submit": "Find my best country",
}
_ASKED = f"What do you mean by *best*?\n\n```clarify\n{json.dumps(_CARD)}\n```"


async def test_a_regenerated_answer_to_a_card_still_answers_it() -> None:
    await engine.dispose(close=False)
    now = datetime.now(UTC)
    lines = [
        ("user", "what's the best country to live in?"),
        ("assistant", _ASKED),
        ("user", "Europe"),
        ("assistant", "Here are the best options in Europe."),
    ]
    async with SessionLocal() as session:
        user = User(email=f"{uuid4()}@example.com", name="Regenerate", google_sub=str(uuid4()))
        session.add(user)
        await session.flush()
        chat = Chat(user_id=user.id, title="Card")
        session.add(chat)
        await session.flush()
        session.add_all(
            Message(
                chat_id=chat.id,
                user_id=user.id,
                role=role,
                content=content,
                model="free-chat" if role == "assistant" else None,
                created_at=now - timedelta(seconds=len(lines) - index),
            )
            for index, (role, content) in enumerate(lines)
        )
        await session.commit()
        user_id, chat_id = user.id, chat.id
    try:
        turn = await load_regenerate_turn(
            default_deps(),
            fakeredis.aioredis.FakeRedis(decode_responses=True),
            get_settings(),
            user_id=user_id,
            chat_id=chat_id,
            model_alias=None,
        )
        assert turn.content == "Europe"
        assert turn.turn_mode.after_card
        assert turn.turn_mode.rich_context
    finally:
        async with SessionLocal() as session:
            await users_repo.delete_user(session, user_id)
        await engine.dispose(close=False)
