from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit
from app.models.schemas import WebSearchClassification
from app.modules.web_search import augment_prompt_messages, should_web_search, web_search_skip


@pytest.mark.asyncio
async def test_should_web_search_classifier_yes_for_factual_lookup():
    settings = Settings(
        mock_llm_enabled=True,
        openrouter_api_key="",
        web_search_classifier_enabled=True,
    )
    assert await should_web_search("Who is the CEO of Anthropic?", settings) is True


@pytest.mark.asyncio
async def test_should_web_search_classifies_a_release_question():
    settings = Settings(web_search_enabled=True, web_search_classifier_enabled=True)
    with patch(
        "app.modules.web_search.detection.classify_web_search",
        AsyncMock(return_value=WebSearchClassification(needs_search=True, query="next iPhone")),
    ) as classify:
        assert await should_web_search("When is the next iPhone coming out?", settings) is True
    classify.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "how's your day",
        "tell me a joke",
        "that's funny",
        "what do you think",
        "how?",
    ],
)
async def test_chitchat_skips_the_search_classifier(query: str):
    settings = Settings(web_search_enabled=True, web_search_classifier_enabled=True)
    with patch(
        "app.modules.web_search.detection.classify_web_search",
        AsyncMock(),
    ) as classify:
        assert await should_web_search(query, settings) is False
    classify.assert_not_awaited()


@pytest.mark.asyncio
async def test_live_cue_still_reaches_the_search_classifier():
    settings = Settings(web_search_enabled=True, web_search_classifier_enabled=True)
    with patch(
        "app.modules.web_search.detection.classify_web_search",
        AsyncMock(return_value=WebSearchClassification(needs_search=True, query="openai ceo")),
    ) as classify:
        assert await should_web_search("who is the ceo of openai", settings) is True
    classify.assert_awaited_once()


@pytest.mark.asyncio
async def test_weather_stays_on_the_instant_yes_path():
    settings = Settings(web_search_enabled=True, web_search_classifier_enabled=True)
    with patch(
        "app.modules.web_search.detection.classify_web_search",
        AsyncMock(),
    ) as classify:
        assert await should_web_search("what's the weather", settings) is True
    classify.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_reminder_after_a_search_does_not_reach_the_classifier():
    settings = Settings(web_search_enabled=True, web_search_classifier_enabled=True)
    prior = ["What is the current price of Bitcoin in US dollars?"]
    with patch(
        "app.modules.web_search.detection.classify_web_search",
        AsyncMock(),
    ) as classify:
        assert (
            await should_web_search(
                "Remind me to water the plant tomorrow at 8:00 AM.",
                settings,
                prior_user_messages=prior,
            )
            is False
        )
        assert (
            await should_web_search(
                "What reminders do I have?",
                settings,
                prior_user_messages=prior,
            )
            is False
        )
    classify.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_memory_question_does_not_continue_an_older_search():
    settings = Settings(web_search_enabled=True, web_search_classifier_enabled=True)
    prior = [
        "What is the current price of Bitcoin in US dollars?",
        "Remember that my dog's name is Kofi and he is a brown terrier.",
    ]
    with patch(
        "app.modules.web_search.detection.classify_web_search",
        AsyncMock(),
    ) as classify:
        assert (
            await should_web_search(
                "What is my dog's name and what color is he?",
                settings,
                prior_user_messages=prior,
            )
            is False
        )
    classify.assert_not_awaited()


@pytest.mark.asyncio
async def test_short_followup_to_a_search_still_reaches_the_classifier():
    settings = Settings(web_search_enabled=True, web_search_classifier_enabled=True)
    with patch(
        "app.modules.web_search.detection.classify_web_search",
        AsyncMock(return_value=WebSearchClassification(needs_search=True, query="paris weather")),
    ) as classify:
        assert (
            await should_web_search(
                "and tomorrow?",
                settings,
                prior_user_messages=["What's the latest news on SpaceX?"],
            )
            is True
        )
    classify.assert_awaited_once()


@pytest.mark.asyncio
async def test_should_web_search_classifier_no_for_stable_topic():
    settings = Settings(
        mock_llm_enabled=True,
        openrouter_api_key="",
        web_search_classifier_enabled=True,
    )
    assert await should_web_search("Explain how recursion works in Python", settings) is False


@pytest.mark.asyncio
async def test_should_web_search_skips_classifier_for_plain_personal_disclosure():
    settings = Settings(web_search_enabled=True, web_search_classifier_enabled=True)
    with patch(
        "app.modules.web_search.detection.classify_web_search",
        AsyncMock(),
    ) as classify:
        assert (
            await should_web_search(
                "I work at Uber but I want to change to Google",
                settings,
            )
            is False
        )
    classify.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "We need a hotel in Paris",
        "Our team needs current API pricing",
    ],
)
async def test_collective_implicit_request_reaches_web_search_classifier(query):
    settings = Settings(web_search_enabled=True, web_search_classifier_enabled=True)
    assert web_search_skip(query) is False
    with patch(
        "app.modules.web_search.detection.classify_web_search",
        AsyncMock(return_value=WebSearchClassification(needs_search=True, query=query)),
    ) as classify:
        assert await should_web_search(query, settings) is True
    classify.assert_awaited_once()


@pytest.mark.asyncio
async def test_should_web_search_skips_classifier_for_personal_memory_question():
    settings = Settings(web_search_enabled=True, web_search_classifier_enabled=True)
    with patch(
        "app.modules.web_search.detection.classify_web_search",
        AsyncMock(),
    ) as classify:
        assert (
            await should_web_search(
                "Where do I work right now, and which company am I considering for the future?",
                settings,
            )
            is False
        )
    classify.assert_not_awaited()


@pytest.mark.asyncio
async def test_should_web_search_fast_path_skips_classifier():
    settings = Settings(
        mock_llm_enabled=True,
        openrouter_api_key="",
        web_search_classifier_enabled=True,
    )
    with patch(
        "app.modules.web_search.classify.classify_web_search_need",
        AsyncMock(),
    ) as classify:
        assert await should_web_search("search the web for AI news", settings) is True
        classify.assert_not_awaited()


@pytest.mark.asyncio
async def test_should_web_search_classifier_disabled_uses_heuristic():
    settings = Settings(web_search_classifier_enabled=False)
    assert await should_web_search("What is the latest price of Bitcoin?", settings) is True


@pytest.mark.asyncio
async def test_should_web_search_falls_back_when_classifier_fails():
    settings = Settings(mock_llm_enabled=False, web_search_classifier_enabled=True)
    with patch(
        "app.modules.web_search.classify.classify_web_search_need",
        AsyncMock(return_value=None),
    ):
        assert await should_web_search("What is the latest price of Bitcoin?", settings) is True


@pytest.mark.asyncio
async def test_classify_web_search_need_skips_llm_when_spend_capped():
    from app.modules.web_search.classify import classify_web_search_need

    settings = Settings(
        mock_llm_enabled=False,
        web_search_classifier_enabled=True,
        daily_global_spend_usd=1.0,
    )
    with (
        patch(
            "app.modules.web_search.classify.quota_service.global_spend_exceeded",
            AsyncMock(return_value=True),
        ),
        patch(
            "app.modules.web_search.classify.litellm_gateway.complete_structured",
            AsyncMock(),
        ) as complete,
        patch("app.modules.web_search.classify.get_redis_client", return_value=AsyncMock()),
    ):
        assert await classify_web_search_need(settings, "Who is the CEO of Anthropic?") is None
    complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_classify_web_search_need_records_global_spend():
    from app.models.schemas import WebSearchClassification
    from app.modules.web_search.classify import classify_web_search_need

    settings = Settings(mock_llm_enabled=False, web_search_classifier_enabled=True)
    classification = WebSearchClassification(needs_search=True, query="anthropic ceo")
    record = AsyncMock()
    with (
        patch(
            "app.modules.web_search.classify.quota_service.global_spend_exceeded",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.modules.web_search.classify.litellm_gateway.complete_structured",
            AsyncMock(return_value=classification),
        ),
        patch("app.modules.web_search.classify.quota_service.record_global_spend", record),
        patch("app.modules.web_search.classify.get_redis_client", return_value=AsyncMock()),
    ):
        result = await classify_web_search_need(settings, "Who is the CEO of Anthropic?")
    assert result == classification
    record.assert_awaited_once()


@pytest.mark.asyncio
async def test_augment_prompt_classifier_routes_factual_lookup(fake_redis):
    settings = Settings(
        mock_llm_enabled=True,
        openrouter_api_key="",
        web_search_classifier_enabled=True,
        mcp_tool_loop_enabled=False,
    )
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": "Who is the CEO of OpenAI?"},
    ]
    with (
        patch("app.modules.web_search.search_cache.get_redis_client", return_value=fake_redis),
        patch(
            "app.modules.web_search.search_cache.web_search_gateway.search_web",
            AsyncMock(
                return_value=[WebSearchHit(title="CEO", url="https://example.com", snippet="Sam")]
            ),
        ) as search_mock,
    ):
        out, hits = await augment_prompt_messages(
            messages,
            "Who is the CEO of OpenAI?",
            settings,
        )
    search_mock.assert_awaited()
    assert "Web search results" in out[-2]["content"]
    assert len(hits) == 1


@pytest.mark.asyncio
async def test_augment_uses_classifier_query_when_present(fake_redis):
    from app.models.schemas import WebSearchClassification

    settings = Settings(
        mock_llm_enabled=True,
        openrouter_api_key="",
        web_search_classifier_enabled=True,
        mcp_tool_loop_enabled=False,
    )
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": "Who runs that company?"},
    ]
    with (
        patch("app.modules.web_search.search_cache.get_redis_client", return_value=fake_redis),
        patch(
            "app.modules.web_search.augment.classify_web_search",
            AsyncMock(
                return_value=WebSearchClassification(
                    needs_search=True,
                    query="OpenAI CEO 2026",
                )
            ),
        ),
        patch(
            "app.modules.web_search.search_cache.web_search_gateway.search_web",
            AsyncMock(
                return_value=[WebSearchHit(title="CEO", url="https://example.com", snippet="Sam")]
            ),
        ) as search_mock,
    ):
        await augment_prompt_messages(
            messages,
            "Who runs that company?",
            settings,
        )
    search_mock.assert_awaited()
    assert search_mock.await_args is not None
    assert search_mock.await_args.args[1] == "OpenAI CEO 2026"
