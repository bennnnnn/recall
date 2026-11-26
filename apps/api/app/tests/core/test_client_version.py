"""The app build a request names reaches its logs and the code it runs (security review,
2026-11-25): a fence an older build cannot draw can at least be told apart by build."""

from __future__ import annotations

import logging

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from app.core.client_version import app_version_context
from app.core.logging import _RequestIdFormatter
from app.core.request_id import RequestIdMiddleware


async def _http(_request: Request) -> JSONResponse:
    logging.getLogger("t").info("inside")
    return JSONResponse({"app_version": app_version_context.get()})


async def _socket(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"app_version": app_version_context.get()})
    await websocket.close()


def _client() -> TestClient:
    app = Starlette(routes=[Route("/v", _http), WebSocketRoute("/ws", _socket)])
    app.add_middleware(RequestIdMiddleware)
    return TestClient(app)


@pytest.mark.parametrize(
    "header, seen",
    [
        ("1.0.0+42", "1.0.0+42"),
        ("1.2.3", "1.2.3"),
        (None, None),
        # Never written into a log as sent.
        ("1.0.0\nforged=1", None),
        ("x" * 33, None),
        ("1.0.0 (42)", None),
    ],
)
def test_the_requests_build_is_read_once_and_only_well_formed(
    header: str | None, seen: str | None
) -> None:
    headers = {"X-App-Version": header} if header is not None else {}
    assert _client().get("/v", headers=headers).json() == {"app_version": seen}


def test_a_chat_socket_names_its_build_in_the_query() -> None:
    with _client().websocket_connect("/ws?app_version=1.0.0%2B42") as socket:
        assert socket.receive_json() == {"app_version": "1.0.0+42"}


def test_every_log_line_of_the_request_names_the_build(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="t")
    lines: list[str] = []

    class Keep(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(_RequestIdFormatter().format(record))

    keep = Keep()
    logging.getLogger("t").addHandler(keep)
    try:
        _client().get("/v", headers={"X-App-Version": "1.0.0+42"})
    finally:
        logging.getLogger("t").removeHandler(keep)
    assert any("app_version=1.0.0+42" in line for line in lines)
    assert app_version_context.get() is None  # nothing leaks past the request
