"""WS and SSE must speak the same protocol.

Both transports build every stream event through
`app.services.chat.stream_events`. These tests pin the shared shapes so a new
event (or a new field on `stream_end` / `done`) cannot land on one transport
and silently miss the other — the backend is documented as client-agnostic, and
a future web client binds to this same contract.
"""

import json
import re
from pathlib import Path

import pytest

from app.services.chat import stream_events

_ROUTERS = Path(__file__).resolve().parents[2] / "routers"
_WS = _ROUTERS / "ws.py"
_SSE = _ROUTERS / "chat_stream.py"

# Every event type the protocol defines, and the builder that owns its shape.
_BUILDERS = {
    "start": lambda: stream_events.build_start_event(),
    "token": lambda: stream_events.build_token_event("hi"),
    "status": lambda: stream_events.build_status_event("thinking", None),
    "reasoning": lambda: stream_events.build_reasoning_event("hmm"),
    "stream_end": lambda: stream_events.build_stream_end_payload({}),
    "done": lambda: stream_events.build_done_payload({}),
}


@pytest.mark.parametrize("event_type", sorted(_BUILDERS))
def test_builder_emits_its_declared_type(event_type: str) -> None:
    assert _BUILDERS[event_type]()["type"] == event_type


def test_stream_end_carries_model_fields_when_present() -> None:
    payload = stream_events.build_stream_end_payload(
        {"resolved_model": "smart-chat", "fallback_used": "free-chat"}
    )
    assert payload == {
        "type": "stream_end",
        "resolved_model": "smart-chat",
        "fallback_used": "free-chat",
    }


def test_stream_end_omits_absent_model_fields() -> None:
    assert stream_events.build_stream_end_payload({"resolved_model": None}) == {
        "type": "stream_end"
    }


def test_done_includes_completion_when_interrupted() -> None:
    payload = stream_events.build_done_payload({"message_id": "abc", "completion": "interrupted"})
    assert payload["type"] == "done"
    assert payload["completion"] == "interrupted"
    assert payload["message_id"] == "abc"


def test_done_omits_complete_completion() -> None:
    payload = stream_events.build_done_payload({"message_id": "abc"})
    assert "completion" not in payload


def test_status_detail_is_optional() -> None:
    assert stream_events.build_status_event("searching") == {
        "type": "status",
        "phase": "searching",
    }
    assert stream_events.build_status_event("searching", "cats") == {
        "type": "status",
        "phase": "searching",
        "detail": "cats",
    }


def test_both_transports_are_json_serializable() -> None:
    for build in _BUILDERS.values():
        json.dumps(build())


def _inline_event_types(path: Path) -> set[str]:
    """Event `type` values a router still constructs inline, bypassing the builders."""
    source = path.read_text()
    return set(re.findall(r'"type":\s*"([a-z_]+)"', source))


@pytest.mark.parametrize("router", [_WS, _SSE], ids=["ws", "sse"])
def test_routers_do_not_rebuild_shared_events_inline(router: Path) -> None:
    """`error` stays inline-free too — it has its own builder.

    Only transport-specific failures may be constructed in a router (the SSE
    "failed to save" message), so anything matching a shared event type here
    means the two transports can drift apart again.
    """
    shared = set(_BUILDERS) | {"error"}
    # "error" is exempt: routers still inline transport-specific failures
    # (auth timeout, invalid JSON, "failed to save") alongside the builder.
    inline = _inline_event_types(router) - {"error"}
    leaked = inline & shared
    assert leaked == set(), f"{router.name} builds shared events inline: {sorted(leaked)}"
