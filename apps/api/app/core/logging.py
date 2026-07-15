"""Logging configuration: request-id correlation + PII redaction.

``setup_logging`` installs:

- a formatter that appends ``[request_id=<id>]`` to every log line, reading
  the current request ID from ``request_id_context`` (set by
  ``RequestIdMiddleware``) so log lines for a single request can be correlated;
- a filter that redacts emails and bearer/JWT tokens from log messages before
  they hit the handler, so PII never lands in the log sink.
"""

from __future__ import annotations

import logging
import re

from app.core.request_id import request_id_context

# Matches RFC-5321-ish emails (loose: user@host.tld) and common bearer/JWT
# tokens. Redaction is best-effort -- the goal is to keep PII out of the
# default log sink, not to be exhaustive against every encoding.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+")
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*")
_REDACTED = "[REDACTED]"


class _PIIRedactFilter(logging.Filter):
    """Redact emails and bearer/JWT tokens from log records in-place."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        redacted = _JWT_RE.sub(_REDACTED, msg)
        redacted = _BEARER_RE.sub(_REDACTED, redacted)
        redacted = _EMAIL_RE.sub(_REDACTED, redacted)
        if redacted != msg:
            # Replace the formatted message so handlers that re-format see
            # the redacted version too.
            record.msg = redacted
            record.args = ()
        return True


class _RequestIdFormatter(logging.Formatter):
    """Formatter that appends ``[request_id=<id>]`` when a request ID is set."""

    _BASE_FMT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    _REQ_FMT = "%(asctime)s %(levelname)s [%(name)s] [request_id=%(request_id)s] %(message)s"

    def format(self, record: logging.LogRecord) -> str:
        rid = request_id_context.get()
        if rid:
            record.request_id = rid  # type: ignore[attr-defined]
            self._style._fmt = self._REQ_FMT  # type: ignore[attr-defined]
        else:
            self._style._fmt = self._BASE_FMT  # type: ignore[attr-defined]
        return super().format(record)


def setup_logging() -> None:
    formatter = _RequestIdFormatter()
    root = logging.getLogger()
    # Replace any pre-existing handlers so we don't double-log or keep the
    # default basicConfig handler around.
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(_PIIRedactFilter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
