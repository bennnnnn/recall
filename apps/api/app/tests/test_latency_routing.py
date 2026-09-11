from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway


def test_latency_sensitive_openrouter_kwargs_prefer_low_ttft_provider() -> None:
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    route = litellm_gateway.resolve_route("free-chat")

    kwargs = litellm_gateway._litellm_kwargs(settings, route, latency_sensitive=True)

    assert kwargs["extra_body"] == {"provider": {"sort": "latency"}}


def test_background_openrouter_kwargs_keep_default_provider_routing() -> None:
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    route = litellm_gateway.resolve_route("memory-model")

    kwargs = litellm_gateway._litellm_kwargs(settings, route)

    assert "extra_body" not in kwargs


@pytest.mark.asyncio
async def test_visible_stream_passes_latency_routing_to_litellm() -> None:
    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")

    class OneChunk:
        def __init__(self) -> None:
            self.done = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.done:
                raise StopAsyncIteration
            self.done = True
            delta = MagicMock()
            delta.content = "hello"
            choice = MagicMock()
            choice.delta = delta
            choice.finish_reason = None
            chunk = MagicMock()
            chunk.choices = [choice]
            chunk.usage = None
            return chunk

    completion = AsyncMock(return_value=OneChunk())
    with patch("app.gateways.litellm_gateway.acompletion", completion):
        text = "".join(
            [
                token
                async for token in litellm_gateway._stream_chat_once(
                    settings=settings,
                    model_alias="free-chat",
                    messages=[{"role": "user", "content": "hi"}],
                    max_tokens=10,
                )
            ]
        )

    assert text == "hello"
    call = completion.await_args
    assert call is not None
    assert call.kwargs["extra_body"] == {"provider": {"sort": "latency"}}
