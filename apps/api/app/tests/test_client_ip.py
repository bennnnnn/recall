from unittest.mock import MagicMock

from app.core.client_ip import client_ip
from app.core.config import Settings


def test_client_ip_uses_forwarded_header_when_trusted():
    request = MagicMock()
    request.client.host = "10.0.0.1"
    request.headers = {"x-forwarded-for": "203.0.113.5, 10.0.0.1"}
    settings = Settings(trust_x_forwarded_for=True)

    assert client_ip(request, settings) == "203.0.113.5"


def test_client_ip_ignores_forwarded_header_when_untrusted():
    request = MagicMock()
    request.client.host = "10.0.0.1"
    request.headers = {"x-forwarded-for": "203.0.113.5, 10.0.0.1"}
    settings = Settings(trust_x_forwarded_for=False)

    assert client_ip(request, settings) == "10.0.0.1"


def test_client_ip_falls_back_when_client_missing():
    request = MagicMock()
    request.client = None
    request.headers = {}

    assert client_ip(request, Settings(trust_x_forwarded_for=False)) == "unknown"


def test_client_ip_uses_host_when_forwarded_header_blank():
    request = MagicMock()
    request.client.host = "10.0.0.1"
    request.headers = {"x-forwarded-for": "   "}

    assert client_ip(request, Settings(trust_x_forwarded_for=True)) == "10.0.0.1"
