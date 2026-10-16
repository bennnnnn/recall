"""Golden prompts: ``build_prompt_messages`` returns these messages, byte for byte.

Each case in ``golden/prompt_messages.json`` holds the inputs a turn handed the
builder and the messages it returned. ``battery:`` and ``sweep:`` cases were
recorded on the real turn path (``behavior/harness.py``); ``branch:`` cases reach
each system-prompt section and style-hint rule. A case stores only what differs
from ``defaults``. Message text is stored as indices into one paragraph table
(joined with a blank line), so a hint repeated in every case is stored once.

After an intended prompt change, regenerate the expected messages and review the diff:

    uv run python -m app.tests.modules.chat.test_prompt_golden
"""

from __future__ import annotations

import asyncio
import difflib
import json
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from app.core.config import Settings
from app.models.orm import Chat, User
from app.modules.chat.prompt_builder import build_prompt_messages
from app.modules.chat.prompt_context import _PromptContextBlocks
from app.tests.behavior.sweep import frozen_clock

GOLDEN = Path(__file__).with_name("golden") / "prompt_messages.json"
CHAT_ID = UUID(int=0xC4A7)
USER_ID = UUID(int=0x05E5)
# Gap rows (older than the recent window) are numbered after the window's rows.
_OLDER_FIRST_ID = 10_000
_T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
_SEPARATOR = "\n\n"

Case = dict[str, Any]


class _Session:
    async def __aenter__(self) -> AsyncMock:
        return AsyncMock()

    async def __aexit__(self, *_args: object) -> None:
        return None


def _rows(pairs: list[list[str]], *, first_id: int) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            id=UUID(int=first_id + index),
            role=role,
            content=content,
            created_at=_T0 + timedelta(minutes=first_id + index),
        )
        for index, (role, content) in enumerate(pairs)
    ]


def _row_id(index: int) -> UUID:
    """History row ``index`` as ``_rows`` numbers it; -1 is an id no row has."""
    return UUID(int=1 + index)


def resolve(case: Case, defaults: Case) -> Case:
    """The case's full inputs: its overrides on top of the file's defaults."""
    full = {**defaults, **case}
    for nested in ("user", "settings", "kwargs"):
        full[nested] = {**defaults[nested], **case.get(nested, {})}
    return full


async def render(case: Case) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Run the real builder on resolved inputs, with only IO and the clock stubbed."""
    history = _rows(case["history"], first_id=1)
    older = _rows(case["older"], first_id=_OLDER_FIRST_ID)
    chat = Chat(id=CHAT_ID, user_id=USER_ID, **case["chat"]) if case["chat"] is not None else None
    blocks = _PromptContextBlocks(
        memory_block=case["memory_block"],
        todos_section=case["todos_section"],
        recent_all=history,
        attachment_rag_block=case["attachment_rag_block"],
        chat=chat,
        history_rag_query_vec=[0.0] if case["history_rag_vec"] else None,
    )
    kwargs = dict(case["kwargs"])
    omit = kwargs.pop("omit", None)
    current = kwargs.pop("current", None)
    user = User(id=USER_ID, **case["user"])
    settings = Settings(_env_file=None, **case["settings"])  # type: ignore[call-arg]
    out: dict[str, object] = {}
    stubs = {
        "app.modules.chat.prompt_builder._load_context_blocks": AsyncMock(return_value=blocks),
        "app.modules.chat.prompt_builder.SessionLocal": _Session,
        "app.modules.chat.prompt_context.SessionLocal": _Session,
        # "error": the attachment-chunk probe fails, and the turn goes on without it.
        "app.modules.attachments.service.has_chunks_for_chat": AsyncMock(
            side_effect=RuntimeError("probe") if case["has_chunks"] == "error" else None,
            return_value=case["has_chunks"],
        ),
        "app.modules.chat.prompt_context.messages_repo.count_for_chat": AsyncMock(
            return_value=case["total"]
        ),
        "app.modules.chat.prompt_context.messages_repo.list_before": AsyncMock(return_value=older),
        "app.modules.chat.history_rag.retrieve_for_prompt": AsyncMock(
            return_value=case["history_rag_block"]
        ),
    }
    with frozen_clock(), ExitStack() as stack:
        for target, value in stubs.items():
            stack.enter_context(patch(target, value))
        messages = await build_prompt_messages(
            user,
            CHAT_ID,
            settings,
            chat=chat,
            out=out,
            omit_message_ids={_row_id(i) for i in omit} if omit is not None else None,
            current_user_message_id=_row_id(current) if current is not None else None,
            **kwargs,
        )
    return messages, out


def load_golden() -> tuple[Case, list[str], list[Case]]:
    data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    return data["defaults"], data["paragraphs"], data["cases"]


def expected_of(table: list[str], case: Case) -> list[dict[str, str]]:
    return [
        {"role": role, "content": _SEPARATOR.join(table[int(i)] for i in indices.split())}
        for role, indices in case["expected"]["messages"]
    ]


async def write_golden(defaults: Case, cases: list[Case]) -> None:
    """Render every case with the current code and store that as its expected output."""
    table: list[str] = []
    index_of: dict[str, int] = {}

    def encode(text: str) -> str:
        indices = []
        for paragraph in text.split(_SEPARATOR):
            if paragraph not in index_of:
                index_of[paragraph] = len(table)
                table.append(paragraph)
            indices.append(str(index_of[paragraph]))
        return " ".join(indices)

    stored = []
    for case in cases:
        messages, out = await render(resolve(case, defaults))
        expected = {"messages": [[m["role"], encode(m["content"])] for m in messages], "out": out}
        stored.append({**{k: v for k, v in case.items() if k != "expected"}, "expected": expected})
    data = {"defaults": defaults, "paragraphs": table, "cases": stored}
    GOLDEN.parent.mkdir(exist_ok=True)
    GOLDEN.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _difference(want: list[dict[str, str]], got: list[dict[str, str]]) -> str:
    lines = difflib.unified_diff(
        [f"[{m['role']}] {line}" for m in want for line in m["content"].splitlines()],
        [f"[{m['role']}] {line}" for m in got for line in m["content"].splitlines()],
        "golden",
        "built",
        lineterm="",
        n=1,
    )
    return "\n".join(list(lines)[:60])


_DEFAULTS, _TABLE, _CASES = load_golden() if GOLDEN.is_file() else ({}, [], [])


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _CASES, ids=[case["id"] for case in _CASES])
async def test_prompt_matches_golden(case: Case) -> None:
    messages, out = await render(resolve(case, _DEFAULTS))
    want = expected_of(_TABLE, case)
    assert messages == want, _difference(want, messages)
    assert out == case["expected"]["out"]


def test_golden_cases_cover_every_source() -> None:
    sources = {case["id"].split(":", 1)[0] for case in _CASES}
    assert sources == {"battery", "sweep", "branch"}
    assert len({case["id"] for case in _CASES}) == len(_CASES)


if __name__ == "__main__":
    asyncio.run(write_golden(_DEFAULTS, _CASES))
    print(f"wrote {len(_CASES)} cases to {GOLDEN}")
