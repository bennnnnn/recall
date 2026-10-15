"""Map "a dependency is down or slow" to 503 + Retry-After instead of a bare 500.

Covers the database (pool exhaustion after ``db_pool_timeout_seconds``, a
statement or connect timeout, a dropped or refused connection). Clients retry
a 503 with backoff; a 500 reads as a bug. The exception is still logged with
its traceback; the response body never carries it.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import exc as sa_exc

logger = logging.getLogger(__name__)

UNAVAILABLE_DETAIL = "Service temporarily unavailable. Please retry shortly."
_RETRY_AFTER_SECONDS = "5"

# TimeoutError covers asyncpg's connect and command timeouts (raised as-is,
# not wrapped by SQLAlchemy). ConnectionError covers refused/reset sockets.
UNAVAILABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    sa_exc.TimeoutError,
    sa_exc.OperationalError,
    sa_exc.InterfaceError,
    TimeoutError,
    ConnectionError,
)


async def _unavailable(request: Request, exc: Exception) -> JSONResponse:
    logger.warning(
        "Dependency unavailable on %s %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": UNAVAILABLE_DETAIL},
        headers={"Retry-After": _RETRY_AFTER_SECONDS},
    )


def register_unavailable_handlers(app: FastAPI) -> None:
    for exc_type in UNAVAILABLE_EXCEPTIONS:
        app.add_exception_handler(exc_type, _unavailable)
