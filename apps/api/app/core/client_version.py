"""Which app build sent a request: the phone's ``X-App-Version`` header.

Nothing told the server which build it answered (security review, 2026-11-25), so a reply
using a fence kind added this month drew "Could not render…" on an older build and no log
said which build that was. The phone sends its version and native build on every request
(``apps/mobile/lib/api/appVersionHeader.ts``; on a chat socket, an ``app_version`` query
parameter, since a socket's headers are not every client's to set). ``RequestIdMiddleware``
reads it once per request into ``app_version_context``: every log line of the request names
it (``core/logging.py``), and code a turn runs, finalize included, reads it with
``app_version_context.get()`` (a socket's turn tasks inherit it). No negotiation yet: an
unknown or missing version changes nothing.
"""

from __future__ import annotations

import contextvars
import re
from urllib.parse import parse_qs

from starlette.datastructures import Headers
from starlette.types import Scope

APP_VERSION_HEADER = "X-App-Version"
_APP_VERSION_QUERY = "app_version"

# "1.0.0+42": a version, then its native build. Anything else (spaces, newlines, a long
# value) is dropped, so a client cannot write into the logs.
_APP_VERSION_RE = re.compile(r"^[0-9A-Za-z._+-]{1,32}$")

app_version_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "app_version_context", default=None
)


def client_app_version(scope: Scope) -> str | None:
    """The build the request names, when it names one well-formed; else None."""
    raw = Headers(scope=scope).get(APP_VERSION_HEADER)
    if raw is None and scope["type"] == "websocket":
        query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
        raw = (query.get(_APP_VERSION_QUERY) or [None])[0]
    return raw if raw and _APP_VERSION_RE.fullmatch(raw) else None
