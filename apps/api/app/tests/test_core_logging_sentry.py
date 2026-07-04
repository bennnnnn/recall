import logging
from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.core.logging import setup_logging
from app.core.sentry import init_sentry


def test_setup_logging_configures_root_logger():
    with patch("logging.basicConfig") as basic:
        setup_logging()
    basic.assert_called_once()
    assert basic.call_args.kwargs["level"] == logging.INFO


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
