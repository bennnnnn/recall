"""generate_for_chat: each gate, which failures give the day's slot back, and cleanup.

The daily counter and the spend meter are the real ones over fakeredis, so a
refund shows as the slot coming back. Storage, sessions, repositories and the
provider are recording fakes; ``events`` is the order the turn touched them.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import ExitStack
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from app.core.attachment_limits import MAX_ATTACHMENT_SIZE
from app.core.config import Settings
from app.gateways.storage_gateway import PresignedUpload, UnconfiguredStorageGateway
from app.models.orm import User
from app.modules.images.generation import ImageGenerationError, generate_for_chat
from app.services import quota as quota_service
from app.services.quota import counters

MOD = "app.modules.images.generation"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


class Boom(RuntimeError):
    pass


@dataclass
class Turn:
    """One generate_for_chat call over recording fakes."""

    redis: Any
    settings: dict[str, Any] = field(default_factory=dict)
    chat_found: bool = True
    storage: bool = True
    refs: list[SimpleNamespace] = field(default_factory=list)
    ref_bytes: bytes = PNG
    generated: Any = (PNG, "image/png")
    fail: dict[str, BaseException] = field(default_factory=dict)
    short_links: set[str] = field(default_factory=set)
    prior: SimpleNamespace | None = None
    user: SimpleNamespace = field(default_factory=lambda: SimpleNamespace(id=uuid4(), plan="pro"))
    events: list[tuple[Any, ...]] = field(default_factory=list)
    output_key: str | None = None
    slot_at_delete: list[str | None] = field(default_factory=list)

    def step(self, *event: Any) -> None:
        self.events.append(event)
        if event[0] in self.fail:
            raise self.fail[event[0]]

    def owned_ref(self, **kw: Any) -> SimpleNamespace:
        row = SimpleNamespace(
            id=uuid4(), user_id=self.user.id, content_type="image/png", message_id=None
        )
        row.storage_key = f"{self.user.id}/{row.id}"
        row.__dict__.update(kw)
        self.refs.append(row)
        return row

    async def slot(self) -> str | None:
        return await self.redis.get(counters.daily_key("imggen", self.user.id))

    async def run(self, **kwargs: Any) -> Any:
        turn = self

        class Session:
            async def __aenter__(self) -> Session:
                turn.events.append(("session",))
                return self

            async def __aexit__(self, typ: Any, *_exc: Any) -> None:
                turn.events.append(("session_exit", typ.__name__ if typ else None))

            async def commit(self) -> None:
                turn.step("commit")

        class Gateway:
            async def presign_upload(self, *, user_id: str, content_type: str, size_bytes: int):
                turn.step("presign", content_type, size_bytes)
                out = uuid4()
                turn.output_key = f"{user_id}/{out}"
                return PresignedUpload(
                    attachment_id=str(out),
                    upload_url="",
                    storage_key=turn.output_key,
                    headers={},
                    api_upload=True,
                )

            async def write_bytes(self, key: str, data: bytes) -> None:
                turn.step("write_output" if key == turn.output_key else "write_ref", key)

            async def read_bytes(self, key: str) -> bytes:
                turn.events.append(("read", key))
                return turn.ref_bytes

            async def delete_bytes(self, key: str) -> None:
                turn.slot_at_delete.append(await turn.slot())
                turn.step("delete", key)

        async def get_by_ids(_s: Any, ids: list[UUID], user_id: UUID) -> list[Any]:
            return [r for r in turn.refs if r.id in ids and r.user_id == user_id]

        async def create_message(_s: Any, *, role: str, content: str, commit: bool, **kw: Any):
            turn.step(f"create_{role}", content, commit)
            return SimpleNamespace(id=uuid4(), role=role, content=content, model=kw.get("model"))

        async def link(_s: Any, *, attachment_ids: list[UUID], commit: bool, **_kw: Any) -> int:
            which = "output" if turn.events[-1][0] == "create_assistant" else "refs"
            turn.step(f"link_{which}", len(attachment_ids), commit)
            return len(attachment_ids) - (which in turn.short_links)

        async def provider(_settings: Any, **kw: Any) -> Any:
            turn.step("provider", kw["prompt"], kw["aspect_ratio"], kw["reference_images"])
            if isinstance(turn.generated, BaseException):
                raise turn.generated
            return turn.generated

        async def recorded(name: str, *_a: Any, **kw: Any) -> None:
            turn.step(name, kw.get("commit"))

        async def chat(*_a: Any) -> object | None:
            turn.events.append(("chat",))
            return object() if turn.chat_found else None

        async def last_user(*_a: Any) -> Any:
            turn.events.append(("last_user",))
            return turn.prior

        async def none(*_a: Any, **_kw: Any) -> Any:
            return None

        async def nothing(*_a: Any, **_kw: Any) -> list[Any]:
            return []

        real_spend = quota_service.record_global_spend

        async def spend(redis: Any, usd: float) -> int:
            turn.step("spend", usd)
            return await real_spend(redis, usd)

        def call(name: str) -> Any:
            return lambda *a, **kw: recorded(name, *a, **kw)

        gateway = Gateway() if self.storage else UnconfiguredStorageGateway()
        with ExitStack() as stack:
            for target, value in {
                "SessionLocal": Session,
                "get_storage_gateway": lambda _s: gateway,
                "get_redis_client": lambda: turn.redis,
                "generate_image": provider,
                "chats_repo.get_by_id": chat,
                "messages_repo.get_last_user": last_user,
                "messages_repo.get_by_id": none,
                "messages_repo.create": create_message,
                "attachments_repo.get_by_ids": get_by_ids,
                "attachments_repo.list_for_message_ids": nothing,
                "attachments_repo.create_pending": call("pending"),
                "attachments_repo.insert_verified_clone": call("clone"),
                "attachments_repo.link_to_message": link,
                "attachments_repo.mark_verified": call("mark_verified"),
                "quota_service.record_global_spend": spend,
            }.items():
                stack.enter_context(patch(f"{MOD}.{target}", value))
            kwargs.setdefault("chat_id", uuid4())
            kwargs.setdefault("prompt", "a cat")
            user = cast(User, self.user)
            return await generate_for_chat(Settings(**self.settings), user=user, **kwargs)

    def names(self) -> list[str]:
        return [event[0] for event in self.events]

    def deleted(self) -> list[str]:
        return [event[1] for event in self.events if event[0] == "delete"]


@pytest.fixture
def turn(fake_redis: Any) -> Turn:
    return Turn(redis=fake_redis)


async def _refused(turn: Turn, **kwargs: Any) -> ImageGenerationError:
    with pytest.raises(ImageGenerationError) as caught:
        await turn.run(**kwargs)
    return caught.value


# Each gate in the order generate_for_chat checks them, with its refusal.
_GATES = {
    "flag_off": (404, "Not available"),
    "attachments_off": (503, "Attachments are disabled"),
    "plan_without_pictures": (403, quota_service.IMAGE_GENERATION_NOT_IN_PLAN_MESSAGE),
    "chat_not_found": (404, "Chat not found"),
    "storage_off": (503, "Attachment storage is not configured"),
    "foreign_reference": (404, "Reference image not found"),
    "missing_reference": (404, "Reference image not found"),
    "three_references": (400, "Use at most two reference images"),
    "reference_not_an_image": (400, "Reference must be an image"),
    "reference_unreadable": (400, "Reference image is unavailable or invalid"),
    "spend_cap": (429, quota_service.IMAGE_GENERATION_SPEND_CAP_MESSAGE),
}


async def _close_gate(turn: Turn, case: str) -> list[UUID] | None:
    """Make *case* refuse; returns the reference ids to send, if the gate needs some."""
    if case == "flag_off":
        turn.settings["image_generation_enabled"] = False
    elif case == "attachments_off":
        turn.settings["attachments_enabled"] = False
    elif case == "plan_without_pictures":
        turn.settings["daily_image_generations_pro"] = 0
    elif case == "chat_not_found":
        turn.chat_found = False
    elif case == "storage_off":
        turn.storage = False
    elif case == "foreign_reference":
        return [turn.owned_ref(user_id=uuid4()).id]
    elif case == "missing_reference":
        return [uuid4()]
    elif case == "three_references":
        return [turn.owned_ref().id for _ in range(3)]
    elif case == "reference_not_an_image":
        return [turn.owned_ref(content_type="application/pdf").id]
    elif case == "reference_unreadable":
        turn.ref_bytes = b""
        return [turn.owned_ref().id]
    elif case == "spend_cap":
        turn.settings["daily_global_spend_usd"] = 1.0
        await quota_service.record_global_spend(turn.redis, 2.0)
    return None


@pytest.mark.parametrize("case", list(_GATES))
async def test_generate_for_chat_gates_refuse_before_a_slot_is_taken(turn, case):
    refs = await _close_gate(turn, case)

    error = await _refused(turn, reference_attachment_ids=refs)

    assert (error.status_code, error.detail) == _GATES[case]
    assert await turn.slot() is None
    assert not {"provider", "presign", "commit", "spend"} & set(turn.names())


@pytest.mark.parametrize(
    "first, later",
    [
        ("flag_off", "attachments_off"),
        ("attachments_off", "plan_without_pictures"),
        ("plan_without_pictures", "chat_not_found"),
        ("chat_not_found", "storage_off"),
        ("storage_off", "spend_cap"),
        ("missing_reference", "spend_cap"),
        ("reference_unreadable", "spend_cap"),
    ],
)
async def test_generate_for_chat_the_first_closed_gate_answers(turn, first, later):
    refs = await _close_gate(turn, later)
    refs = await _close_gate(turn, first) or refs

    error = await _refused(turn, reference_attachment_ids=refs)

    assert (error.status_code, error.detail) == _GATES[first]


async def test_generate_for_chat_at_the_daily_cap_refuses_and_keeps_the_count(turn):
    key = counters.daily_key("imggen", turn.user.id)
    await turn.redis.set(key, 15)

    error = await _refused(turn)

    assert (error.status_code, error.detail) == (
        429,
        counters.limit_message("image_generation", turn.user),
    )
    assert await turn.slot() == "15"
    assert "provider" not in turn.names()


_GENERATED_REFUSALS = [
    ("provider_none", None, 502, "Could not generate image"),
    (
        "oversized",
        (PNG + b"\x00" * MAX_ATTACHMENT_SIZE, "image/png"),
        502,
        "Generated image exceeds the maximum allowed size",
    ),
    ("not_an_image", (b"hello", "text/plain"), 502, "Generated file is not an image"),
    ("bytes_mismatch", (b"not a png", "image/png"), 502, "Generated image failed validation"),
]


@pytest.mark.parametrize("case, generated, status, detail", _GENERATED_REFUSALS)
async def test_generate_for_chat_a_refused_result_gives_the_slot_back(
    turn, case, generated, status, detail
):
    turn.generated = generated

    error = await _refused(turn)

    assert (error.status_code, error.detail) == (status, detail)
    assert await turn.slot() == "0"
    assert "presign" not in turn.names()


async def test_generate_for_chat_a_blank_prompt_is_refused_after_the_reserve(turn):
    error = await _refused(turn, prompt="   ")

    assert (error.status_code, error.detail) == (400, "Prompt is required")
    assert await turn.slot() == "0"
    assert "provider" not in turn.names()


@pytest.mark.parametrize(
    "fail_at, with_ref, deleted",
    [
        ("provider", False, []),
        ("presign", False, []),
        ("write_output", False, []),
        ("write_ref", True, ["output"]),
        ("pending", True, ["output", "ref"]),
        ("create_user", True, ["output", "ref"]),
        ("create_assistant", False, ["output"]),
        ("mark_verified", False, ["output"]),
        ("commit", True, ["output", "ref"]),
    ],
)
@pytest.mark.parametrize("error", [Boom("down"), asyncio.CancelledError()])
async def test_generate_for_chat_a_failure_after_the_reserve_refunds_and_deletes_written_bytes(
    turn, fail_at, with_ref, deleted, error
):
    refs = [turn.owned_ref().id] if with_ref else None
    turn.fail[fail_at] = error

    with pytest.raises(type(error)):
        await turn.run(reference_attachment_ids=refs)

    assert await turn.slot() == "0"
    written = {"output": turn.output_key}
    written["ref"] = next((e[1] for e in turn.events if e[0] == "write_ref"), None)
    assert turn.deleted() == [written[name] for name in deleted]
    assert "spend" not in turn.names()


@pytest.mark.parametrize(
    "case, status, detail, deleted",
    [
        ("refs_link_short", 500, "Could not preserve image references", ["output", "ref"]),
        ("output_link_short", 500, "Could not link generated image", ["output", "ref"]),
        ("regenerate_without_user_turn", 404, "No user message to attach image to", ["output"]),
    ],
)
async def test_generate_for_chat_a_persist_refusal_rolls_back_and_refunds(
    turn, case, status, detail, deleted
):
    ref = turn.owned_ref()
    kwargs: dict[str, Any] = {"reference_attachment_ids": [ref.id]}
    if case == "refs_link_short":
        turn.short_links = {"refs"}
    elif case == "output_link_short":
        turn.short_links = {"output"}
    else:
        kwargs["create_user_message"] = False

    error = await _refused(turn, **kwargs)

    assert (error.status_code, error.detail) == (status, detail)
    assert await turn.slot() == "0"
    assert "commit" not in turn.names()
    assert turn.events[-len(deleted) - 1][0] == "session_exit"
    keys = {"output": turn.output_key}
    keys["ref"] = next((e[1] for e in turn.events if e[0] == "write_ref"), None)
    assert turn.deleted() == [keys[name] for name in deleted]


@pytest.mark.parametrize("status, refunded", [(403, False), (429, False), (409, True)])
@pytest.mark.parametrize("fail_at", ["provider", "pending"])
async def test_generate_for_chat_a_403_or_429_inside_the_turn_keeps_the_slot(
    turn, status, refunded, fail_at
):
    turn.fail[fail_at] = ImageGenerationError("refused", status_code=status)

    error = await _refused(turn)

    assert error.status_code == status
    assert await turn.slot() == ("0" if refunded else "1")
    assert turn.deleted() == ([turn.output_key] if fail_at == "pending" else [])


async def test_generate_for_chat_deletes_the_bytes_before_giving_the_slot_back(turn):
    turn.fail["commit"] = Boom("db")

    with pytest.raises(Boom):
        await turn.run(reference_attachment_ids=[turn.owned_ref().id])

    assert turn.slot_at_delete == ["1", "1"]
    assert await turn.slot() == "0"


async def test_generate_for_chat_a_failed_delete_is_logged_and_the_slot_still_refunded(
    turn, caplog
):
    turn.fail["commit"] = Boom("db")
    turn.fail["delete"] = Boom("storage")

    with caplog.at_level(logging.ERROR, logger=MOD), pytest.raises(Boom, match="db"):
        await turn.run()

    assert await turn.slot() == "0"
    assert [r.getMessage() for r in caplog.records] == [
        f"Failed to delete orphaned generated image {turn.output_key}"
    ]


async def test_generate_for_chat_success_commits_one_turn_then_records_spend(turn):
    user_message, assistant_message = await turn.run(prompt=" a cat ")

    assert user_message.content == "Generate image: a cat"
    attachment = turn.output_key.split("/")[1]
    assert assistant_message.content == f"[Image: /attachments/{attachment}/file]"
    assert turn.names() == [
        "session",
        "chat",
        "session_exit",
        "provider",
        "presign",
        "write_output",
        "session",
        "pending",
        "create_user",
        "create_assistant",
        "link_output",
        "mark_verified",
        "commit",
        "session_exit",
        "spend",
    ]
    assert all(e[-1] is False for e in turn.events if e[0].startswith(("pending", "create_")))
    assert await turn.slot() == "1"
    assert await quota_service.get_global_spend_micro_usd(turn.redis) == 30_000


async def test_generate_for_chat_a_users_photo_is_copied_linked_and_shown(turn):
    photo = turn.owned_ref()

    user_message, _ = await turn.run(
        prompt="make it blue",
        user_message_content="Make it blue",
        reference_attachment_ids=[photo.id],
    )

    copy_key = next(e[1] for e in turn.events if e[0] == "write_ref")
    copy_id = copy_key.split("/")[1]
    assert user_message.content == f"Make it blue\n[Image: /attachments/{copy_id}/file]"
    provider = next(e for e in turn.events if e[0] == "provider")
    assert provider[3] == [(PNG, "image/png")]
    assert turn.names()[turn.names().index("pending") :] == [
        "pending",
        "clone",
        "create_user",
        "link_refs",
        "create_assistant",
        "link_output",
        "mark_verified",
        "commit",
        "session_exit",
        "spend",
    ]


async def test_generate_for_chat_regenerate_reuses_the_last_user_turn(turn):
    turn.prior = SimpleNamespace(id=uuid4(), role="user", content="a cat")

    user_message, assistant_message = await turn.run(create_user_message=False)

    assert user_message is turn.prior
    assert assistant_message.role == "assistant"
    assert turn.names().count("last_user") == 2
    assert "create_user" not in turn.names()


async def test_generate_for_chat_a_failed_spend_record_is_logged_not_raised(turn, caplog):
    turn.fail["spend"] = Boom("redis")

    with caplog.at_level(logging.ERROR, logger=MOD):
        user_message, _ = await turn.run()

    assert user_message.role == "user"
    assert await turn.slot() == "1"
    assert [r.getMessage() for r in caplog.records] == [
        "record_global_spend failed after image generation"
    ]
