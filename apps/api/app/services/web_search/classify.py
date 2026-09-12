"""LLM gate for whether a turn needs a live web search."""

from __future__ import annotations

import asyncio
import logging

from app.core.config import Settings
from app.core.redis import get_redis_client
from app.gateways import litellm_gateway, mock_llm
from app.models.schemas import WebSearchClassification
from app.services import quota as quota_service

logger = logging.getLogger(__name__)


async def classify_web_search_need(
    settings: Settings,
    user_message: str,
    *,
    prior_user_messages: list[str] | None = None,
) -> WebSearchClassification | None:
    """Cheap structured gate for ambiguous turns — regex handles obvious cases."""
    budget = settings.web_search_classifier_timeout_seconds
    if budget <= 0:
        return None
    deadline = asyncio.get_running_loop().time() + budget
    try:
        async with asyncio.timeout_at(deadline):
            if mock_llm.should_mock_llm(settings):
                return await mock_llm.mock_web_search_classification(
                    user_message,
                    prior_user_messages=prior_user_messages,
                )
            redis = get_redis_client()
            if await quota_service.global_spend_exceeded(redis, settings):
                return None
    except TimeoutError:
        logger.debug("Web-search classifier spend check exceeded its foreground budget")
        return None

    context_lines: list[str] = []
    if prior_user_messages:
        for msg in prior_user_messages[-2:]:
            stripped = msg.strip()
            if stripped:
                context_lines.append(f"- {stripped[:200]}")
    context_block = "\n".join(context_lines) if context_lines else "(none)"

    messages = [
        {
            "role": "system",
            "content": (
                "You decide if a personal chat assistant should run a live web search "
                "before answering. Return ONLY JSON: "
                '{"needs_search": true|false, "query": "optional concise search query"}.\n\n'
                "When needs_search is true, set query to a short web search string "
                "(5-12 words) that would find the answer — not the user's full message.\n\n"
                "Search YES for: current events, live scores, prices, people/org facts "
                "that change over time, product release info, weather, local venues, "
                "anything needing up-to-date data from the internet.\n\n"
                "Search NO for: coding help, writing/editing, math, trivia the model "
                "knows, personal planning/reminders/lists, app settings, translating, summarizing "
                "pasted text, opinions, creative writing, general explanations of "
                "stable concepts.\n\n"
                "When unsure, prefer false unless the answer likely changed in the last year."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Recent user messages:\n{context_block}\n\n"
                f"Latest message:\n{user_message.strip()[:500]}"
            ),
        },
    ]
    try:
        async with asyncio.timeout_at(deadline):
            result = await litellm_gateway.complete_structured(
                settings=settings,
                model_alias="memory-model",
                messages=messages,
                schema=WebSearchClassification,
                max_tokens=64,
                timeout_seconds=settings.web_search_classifier_timeout_seconds,
                allow_fallback=False,
            )
    except TimeoutError:
        logger.debug("Web-search classifier exceeded its foreground budget")
        return None
    try:
        # All IO shares one deadline. A valid verdict survives an accounting
        # timeout; bookkeeping must not turn a known live-search need into no.
        async with asyncio.timeout_at(deadline):
            await quota_service.record_global_spend(
                redis, quota_service.WEB_SEARCH_CLASSIFIER_SPEND_USD
            )
    except TimeoutError:
        logger.warning("Web-search classifier accounting exceeded its foreground budget")
    except Exception:
        logger.exception("record_global_spend failed after web-search classifier")
    return result
