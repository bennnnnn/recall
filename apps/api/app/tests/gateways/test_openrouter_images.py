"""Tests for app.gateways.openrouter_images."""

from app.core.config import Settings
from app.gateways.openrouter_images import (
    configured_provider_order,
    openrouter_image_headers,
    provider_attempts,
)


def test_openrouter_image_headers_include_referer():
    settings = Settings(openrouter_api_key="sk-or-test")
    headers = openrouter_image_headers(settings)
    assert headers["Authorization"] == "Bearer sk-or-test"
    assert headers["HTTP-Referer"]
    assert headers["X-Title"] == "Recall"


def test_configured_provider_order_splits_csv():
    settings = Settings(image_generation_provider_order="google-vertex, google-ai-studio")
    assert configured_provider_order(settings) == ["google-vertex", "google-ai-studio"]


def test_provider_attempts_uses_workspace_default_then_pins():
    settings = Settings()
    attempts = provider_attempts(
        settings,
        model="google/gemini-2.5-flash-image",
        endpoint_slugs=["google-ai-studio"],
    )
    assert attempts[0] is None
    assert attempts[1] == {"order": ["google-vertex"], "allow_fallbacks": True}
    assert attempts[2] == {"order": ["google-ai-studio"], "allow_fallbacks": True}


def test_provider_attempts_honors_explicit_order():
    settings = Settings(image_generation_provider_order="bytedance")
    attempts = provider_attempts(settings, model="any-model", endpoint_slugs=[])
    assert attempts == [{"order": ["bytedance"], "allow_fallbacks": True}]
