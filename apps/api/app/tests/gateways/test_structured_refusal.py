"""A foreground structured call (no fallback for outages) still asks the fallback when its
model refuses at once, within what is left of its own budget."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.gateways import litellm_gateway


class _Read(BaseModel):
    answer: str


# The errors LiteLLM raises for an OpenRouter call, as the gateway sees them.
def _rate_limited() -> Exception:
    return litellm.RateLimitError(message="429", llm_provider="openrouter", model="m")


def _unavailable() -> Exception:
    return litellm.ServiceUnavailableError(message="503", llm_provider="openrouter", model="m")


def _server_error() -> Exception:
    return litellm.InternalServerError(message="500", llm_provider="openrouter", model="m")


def _dropped() -> Exception:
    # LiteLLM gives a dropped connection status 500: it reads as a server fault and, with
    # time left, hands over like one.
    return litellm.APIConnectionError(message="reset", llm_provider="openrouter", model="m")


def _timed_out() -> Exception:
    return litellm.Timeout(message="slow", model="m", llm_provider="openrouter")


def _bad_request() -> Exception:
    return litellm.BadRequestError(message="400", model="m", llm_provider="openrouter")


def _reply(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


async def _call(
    primary: BaseException,
    timeout_seconds: float,
    *,
    quiet_timeout: bool = False,
    refusal_fallback: bool = True,
    refused_after: float = 0.0,
    fallback_takes: float = 0.0,
) -> tuple[list[str], _Read | None]:
    """The models asked and the result, when the primary raises ``primary``."""
    asked: list[str] = []

    async def acompletion(**kwargs: Any) -> MagicMock:
        asked.append(kwargs["model"])
        if len(asked) == 1:
            await asyncio.sleep(refused_after)
            raise primary
        await asyncio.sleep(fallback_takes)
        return _reply('{"answer": "from the fallback"}')

    settings = Settings(mock_llm_enabled=False, openrouter_api_key="sk-or-test")
    with patch.object(litellm_gateway, "acompletion", AsyncMock(side_effect=acompletion)):
        result = await litellm_gateway.complete_structured(
            settings=settings,
            model_alias="title-model",
            messages=[{"role": "user", "content": "Top 5 in Ethiopia"}],
            schema=_Read,
            timeout_seconds=timeout_seconds,
            allow_fallback=False,
            quiet_timeout=quiet_timeout,
            refusal_fallback=refusal_fallback,
        )
    return asked, result


@pytest.mark.asyncio
@pytest.mark.parametrize("refusal", [_rate_limited, _unavailable, _server_error, _dropped])
async def test_a_refusal_asks_the_fallback(refusal: Any) -> None:
    asked, result = await _call(refusal(), timeout_seconds=3.0)
    assert [model.rsplit("/", 1)[-1] for model in asked] == ["qwen3.7-flash", "claude-haiku-5.5"]
    assert result == _Read(answer="from the fallback")


@pytest.mark.asyncio
async def test_the_fallback_gets_what_is_left_of_the_budget_not_a_new_one() -> None:
    # Refused after 1 s of a 2 s budget: a fallback taking 1.5 s runs out of the 1 s left.
    asked, result = await _call(
        _rate_limited(), timeout_seconds=2.0, refused_after=1.0, fallback_takes=1.5
    )
    assert len(asked) == 2
    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        TimeoutError,  # slow, not refused: the caller's deadline is spent
        _timed_out,  # the provider's own timeout, the same
        _bad_request,  # a bad request fails on any model
    ],
)
async def test_no_fallback_for_a_failure_that_is_no_refusal(error: Any) -> None:
    asked, result = await _call(error(), timeout_seconds=3.0)
    assert len(asked) == 1
    assert result is None


@pytest.mark.asyncio
async def test_no_fallback_when_too_little_of_the_budget_is_left() -> None:
    asked, _ = await _call(_rate_limited(), timeout_seconds=0.5)
    assert len(asked) == 1


@pytest.mark.asyncio
async def test_a_caller_can_keep_its_own_model() -> None:
    # The model reader's shadow measures one model; another's read would be recorded as its.
    asked, _ = await _call(_rate_limited(), timeout_seconds=3.0, refusal_fallback=False)
    assert len(asked) == 1


@pytest.mark.asyncio
async def test_a_quiet_read_still_hands_over() -> None:
    # The referent and posed reads log a timeout quietly, and still want an answer.
    asked, result = await _call(_rate_limited(), timeout_seconds=3.0, quiet_timeout=True)
    assert len(asked) == 2 and result is not None
