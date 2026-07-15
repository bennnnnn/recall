import logging
from unittest.mock import MagicMock

from app.core.config import Settings
from app.core.logging import _PIIRedactFilter, _RequestIdFormatter, setup_logging
from app.core.request_id import request_id_context
from app.core.sentry import init_sentry


def test_setup_logging_configures_root_logger_level():
    """setup_logging must set the root logger to INFO level."""
    root = logging.getLogger()
    prior_level = root.level
    prior_handlers = list(root.handlers)
    try:
        setup_logging()
        assert root.level == logging.INFO
    finally:
        root.setLevel(prior_level)
        root.handlers = prior_handlers


def test_setup_logging_installs_handler_with_formatter_and_filter():
    """setup_logging must install a handler carrying the request-id formatter
    and the PII redaction filter — the two things that make logs safe to ship."""
    root = logging.getLogger()
    # Snapshot existing handlers so we can restore them after the test.
    prior = list(root.handlers)
    try:
        setup_logging()
        assert root.handlers, "expected at least one handler after setup_logging"
        has_formatter = any(isinstance(h.formatter, _RequestIdFormatter) for h in root.handlers)
        has_filter = any(
            any(isinstance(f, _PIIRedactFilter) for f in h.filters) for h in root.handlers
        )
        assert has_formatter, "no handler carries _RequestIdFormatter"
        assert has_filter, "no handler carries _PIIRedactFilter"
    finally:
        root.handlers = prior


def test_pii_redact_filter_redacts_emails():
    """Emails in log messages must be replaced with [REDACTED]."""
    rec = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="user alice@example.com logged in",
        args=(),
        exc_info=None,
    )
    _PIIRedactFilter().filter(rec)
    assert "alice@example.com" not in rec.getMessage()
    assert "[REDACTED]" in rec.getMessage()


def test_pii_redact_filter_redacts_bearer_tokens():
    rec = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="auth: Bearer abc.def.ghi",
        args=(),
        exc_info=None,
    )
    _PIIRedactFilter().filter(rec)
    assert "Bearer abc.def.ghi" not in rec.getMessage()
    assert "[REDACTED]" in rec.getMessage()


def test_pii_redact_filter_redacts_jwt_tokens():
    """Raw JWTs (eyJ...) must be redacted even without a 'Bearer' prefix."""
    rec = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.signature",
        args=(),
        exc_info=None,
    )
    _PIIRedactFilter().filter(rec)
    assert "eyJhbGciOiJIUzI1NiJ9" not in rec.getMessage()
    assert "[REDACTED]" in rec.getMessage()


def test_request_id_formatter_includes_request_id_when_set():
    """When request_id_context is set, the formatter must include it in the line."""
    rec = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    token = request_id_context.set("req-abc-123")
    try:
        line = _RequestIdFormatter().format(rec)
    finally:
        request_id_context.reset(token)
    assert "request_id=req-abc-123" in line
    assert "hello" in line


def test_request_id_formatter_omits_request_id_when_unset():
    """When no request ID is in context, the formatter must NOT add the field."""
    rec = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    # Ensure no request ID is set in this context.
    token = request_id_context.set(None)
    try:
        line = _RequestIdFormatter().format(rec)
    finally:
        request_id_context.reset(token)
    assert "request_id=" not in line
    assert "hello" in line


def test_init_sentry_noops_without_dsn():
    init_sentry(Settings(sentry_dsn=""))


def test_init_sentry_handles_missing_sdk(monkeypatch):
    import app.core.sentry as sentry_mod

    monkeypatch.setattr(sentry_mod, "_initialized", False)
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "sentry_sdk":
            raise ImportError("no sentry")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    sentry_mod.init_sentry(Settings(sentry_dsn="https://example@sentry.io/1"))


def test_init_sentry_initializes_when_configured(monkeypatch):
    import app.core.sentry as sentry_mod

    monkeypatch.setattr(sentry_mod, "_initialized", False)
    init_mock = MagicMock()
    fake_sdk = MagicMock()
    fake_sdk.init = init_mock
    monkeypatch.setitem(__import__("sys").modules, "sentry_sdk", fake_sdk)
    monkeypatch.setitem(
        __import__("sys").modules,
        "sentry_sdk.integrations.fastapi",
        MagicMock(FastApiIntegration=MagicMock()),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "sentry_sdk.integrations.starlette",
        MagicMock(StarletteIntegration=MagicMock()),
    )

    sentry_mod.init_sentry(Settings(sentry_dsn="https://example@sentry.io/1", environment="test"))

    init_mock.assert_called_once()
    assert sentry_mod._initialized is True
