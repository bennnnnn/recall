"""The Decider's call through OpenRouter (``decider_gateway``), with no network."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.gateways import decider_gateway
from app.tests.fakes import isolated_settings


def _client(payload: dict[str, Any]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_the_answers_are_validated_and_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(
        {
            "answers": {
                "subject": {"type": "choice", "choice": "physics", "confidence": 0.97},
                "hard": {"type": "noul", "noul": 0.93},
            },
            "usage": {"input_tokens": 262, "cost": 5.2e-06},
        }
    )
    monkeypatch.setattr(decider_gateway, "get_pooled_client", lambda _timeout: client)
    reply = await decider_gateway.decide(
        isolated_settings(openrouter_api_key="sk-or-test"),
        model="perplexity/pplx-decider-v1.2",
        state="The user's last message: hi",
        questions={"hard": {"type": "noul", "instructions": "hard?"}},
        seconds=1.0,
    )
    assert reply.answers["subject"].choice == "physics"
    assert reply.answers["hard"].noul == 0.93 and reply.usage.cost == 5.2e-06
    body = client.post.await_args.kwargs["json"]
    assert body["model"] == "perplexity/pplx-decider-v1.2" and "hard" in body["questions"]
    assert client.post.await_args.kwargs["timeout"] == 1.0


@pytest.mark.asyncio
async def test_no_key_never_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client({})
    monkeypatch.setattr(decider_gateway, "get_pooled_client", lambda _timeout: client)
    with pytest.raises(RuntimeError):
        await decider_gateway.decide(
            isolated_settings(openrouter_api_key=""), model="m", state="s", questions={}, seconds=1
        )
    client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_answer_out_of_shape_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        decider_gateway, "get_pooled_client", lambda _timeout: _client({"answers": "nope"})
    )
    with pytest.raises(ValueError):
        await decider_gateway.decide(
            isolated_settings(openrouter_api_key="k"), model="m", state="s", questions={}, seconds=1
        )
