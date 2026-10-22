"""Model providers and every model call: keys, timeouts, fallbacks, output cap, tool loop."""

from pydantic import BaseModel


class LlmSettings(BaseModel):
    openrouter_api_key: str = ""
    # Direct OpenAI key for all voice: dictation, read-aloud and Live Talk WebRTC.
    openai_api_key: str = ""
    # Model-initiated LiteLLM tools= loop. Ordinary chat streams immediately;
    # the loop runs only when the turn still looks like search / unsolved math /
    # Pro image gen after heuristic inject.
    mcp_tool_loop_enabled: bool = True
    mcp_tool_loop_max_rounds: int = 2
    mcp_tool_loop_timeout_seconds: float = 8.0
    # Tool selection returns calls or a no-tool decision, not the final answer.
    mcp_tool_loop_probe_max_tokens: int = 1024
    mcp_tool_loop_max_calls_per_round: int = 4
    mcp_tool_loop_invoke_timeout_seconds: float = 20.0

    # Background LLM resilience: if the primary memory-model provider is down,
    # retry background jobs (memory/todo/project extraction, titles, summaries)
    # once against this alias. Empty disables the fallback.
    memory_fallback_model_alias: str = "fallback-memory-model"
    # Hard ceiling on a single turn's output tokens. This is a safety backstop
    # against runaway generation and cost, NOT a response-style throttle —
    # brevity is driven by the STYLE_HINTS prompt guidance (short/balanced/
    # detailed). Set high enough that real deliverables (HTML pages, graph
    # JSON, long code) complete instead of truncating mid-fence. The daily
    # token quota (plans.py) is the real per-user cost guardrail. Keep deployed
    # environment overrides aligned with this 8192 default; lower legacy caps
    # can cut advanced derivations off mid-step.
    max_output_tokens: int = 8192
    # Send the chat prompt's stable system message with a cache_control mark to the
    # models that cache only a marked prefix (catalog cache_breakpoints: Claude). Off
    # sends it unmarked; providers that reuse a repeated prefix on their own still do.
    prompt_cache_breakpoints_enabled: bool = True
    # Provider embedding-input char cap (embedding_gateway.embed_text). Was a
    # bare `text[:8000]` inline in the gateway; every other tunable in this
    # codebase lives in Settings, so don't reintroduce an inline magic number
    # here — change this constant instead.
    embedding_input_max_chars: int = 8000
    # embed_many (attachment/chat-history index, memory): inputs per provider
    # request, and requests in flight.
    embedding_batch_size: int = 64
    embedding_concurrency: int = 8

    # Abort a provider stream after this many seconds with no new chunk (fly.toml
    # sets 30). A stall mid-reply froze the bubble for 3 min; the phone says
    # "still working" at 20 s. Reasoning chunks count, and the cap below applies.
    chat_stream_timeout_seconds: int = 45
    # Hard cap on one provider stream (seconds). Stops a slow drip from holding
    # the chatprep lock, RAM, and the OpenRouter meter indefinitely.
    chat_stream_max_seconds: int = 600
    # Fail fast when the provider never opens an SSE stream (separate from read timeout).
    chat_stream_connect_timeout_seconds: int = 15
    # Reasoning models can keep sending hidden chain-of-thought while never
    # producing a user-visible token. When a fallback exists, stop that silent
    # attempt and move on rather than making the chat bubble wait indefinitely.
    chat_stream_first_content_timeout_seconds: float = 8.0

    # Abort hung background (non-streaming) LLM calls after this many seconds.
    # Covers title generation, memory extraction, todos, summaries — a hung
    # provider would otherwise stall the job worker indefinitely.
    background_llm_timeout_seconds: int = 60
    # Dev placeholder: canned replies when no provider key is set. Production
    # boot refuses it (validate_production_settings).
    mock_llm_enabled: bool = True
