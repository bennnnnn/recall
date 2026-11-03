"""The installed LiteLLM answers a request that carries tools, offline.

Every reply the tool loop leaves alone offers `web_search` (reply_calls.py), so a LiteLLM
that cannot take tools fails every chat. litellm 1.106 imports its MCP bridge, and through
it the `mcp` package, for any request with tools, though `mcp` is only in its `proxy` and
`mcp` extras: each such reply raised "No module named 'mcp'" ("That model isn't responding
right now"). The gateway tests stub LiteLLM, so only this one runs the real package.
"""

import litellm
import pytest

WEB_SEARCH = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_litellm_answers_a_request_with_tools_offline(stream: bool) -> None:
    response = await litellm.acompletion(
        model="openrouter/openai/gpt-4o-mini",
        messages=[{"role": "user", "content": "Why is the sky blue?"}],
        tools=[WEB_SEARCH],
        stream=stream,
        mock_response="Rayleigh scattering.",
        api_key="test-key",
    )
    if stream:
        text = "".join([chunk.choices[0].delta.content or "" async for chunk in response])
    else:
        text = response.choices[0].message.content
    assert text == "Rayleigh scattering."
