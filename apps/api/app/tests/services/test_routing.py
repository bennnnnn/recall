"""Tests for app.services.routing — pure functions, no I/O needed."""

import time

import pytest

from app.core.config import Settings
from app.services import model_catalog, routing
from app.services import plan as plan_service
from app.services.routing import resolve_alias, resolve_alias_in_pool, route_chat_model


@pytest.mark.parametrize(
    "content,expected",
    [
        # Simple messages → free-chat
        ("hi", "free-chat"),
        ("hello world", "free-chat"),
        ("what's for lunch", "free-chat"),
        ("explain quantum computing", "free-chat"),
        ("why is the sky blue", "free-chat"),
        ("compare two options", "free-chat"),
        # Smart triggers → smart-chat
        ("prove p = np", "smart-chat"),
        ("debug the memory leak", "smart-chat"),
        ("analyze this algorithm", "smart-chat"),
        ("design a distributed queue", "smart-chat"),
        ("derive the formula", "smart-chat"),
        ("refactor this module", "smart-chat"),
        ("step by step how to deploy", "smart-chat"),
        ("optimize this query", "smart-chat"),
        ("trade-off between latency and throughput", "smart-chat"),
        ("what is the complexity of this", "smart-chat"),
        # Comparison cues → smart-chat (previously classifier-only web search
        # with no model upgrade; a weak model answered "X vs Y" questions).
        ("kenya vs ethiopia", "smart-chat"),
        ("react versus vue for a production app", "smart-chat"),
        # Bare coding asks without a fence → smart-chat (previously stayed
        # free-chat because there was no ``` fence and no smart keyword).
        ("write a function to merge two sorted lists", "smart-chat"),
        ("write a script that backs up my db", "smart-chat"),
        ("implement a rate limiter in python", "smart-chat"),
        ("code a rest api for todos", "smart-chat"),
        ("solve this leetcode problem", "smart-chat"),
        # Long message (>=800 chars → smart-chat)
        ("a" * 801, "smart-chat"),
        ("a" * 799, "free-chat"),
        # Any code fence → smart-chat, regardless of language tag (or lack of
        # one). BUG FIX: this used to only match a fixed language allowlist,
        # so a bare fence or an unlisted language (bash, shell, C, HTML, ...)
        # silently stayed on free-chat even with real pasted code.
        ("check this:\n```python\nprint(1)\n```", "smart-chat"),
        ("check this out:\n```\nprint(1)\n```", "smart-chat"),
        ("run this:\n```bash\necho hi\n```", "smart-chat"),
        ("what's wrong here:\n```html\n<div></div>\n```", "smart-chat"),
        # Math / structured turns → smart-chat (a weak model on a math ask
        # produced wrong worked steps even with SymPy-verified fences).
        ("solve 2x + 3 = 7", "smart-chat"),
        ("graph y = x^2", "smart-chat"),
        ("2x+3=7", "smart-chat"),
        ("find the area of a circle radius 4", "smart-chat"),
        ("integrate x^2 from 0 to 1", "smart-chat"),
        ("standard deviation of 1, 2, 3, 4, 5", "smart-chat"),
        # Verified closed-form arithmetic stays free-chat — R1 used to dump a
        # live Reasoning essay ("the user just wrote 4!") on these.
        ("4!", "free-chat"),
        ("what is 1+1", "free-chat"),
        ("3+0", "free-chat"),
        ("3 + 0", "free-chat"),
        # Homework physics the solver templates don't cover → smart-chat.
        # needs_symbolic stays false on these (no verified fence); Auto still
        # escalates. Bare "physics" and digit-free "momentum" stay free-chat.
        (
            "a 2kg block slides down a 30° frictionless incline, find its acceleration",
            "smart-chat",
        ),
        ("calculate the momentum of a 5kg object moving at 12 m/s", "smart-chat"),
        ("what is the escape velocity of earth", "smart-chat"),
        ("equations of motion for a pendulum", "smart-chat"),
        ("physics", "free-chat"),
        ("the project has momentum now", "free-chat"),
        # Plain prose with no math cue stays free-chat.
        ("what's for dinner tonight", "free-chat"),
    ],
)
def test_route_chat_model(content: str, expected: str) -> None:
    assert route_chat_model(content) == expected


@pytest.mark.parametrize(
    "content,prior_user,expected",
    [
        ("Now fix it", None, "free-chat"),
        ("Now fix it", "debug this algorithm", "smart-chat"),
        ("add tests", "debug this algorithm", "smart-chat"),
        ("check if it is fixed", "debug this algorithm", "smart-chat"),
        ("Handle the edge cases", "debug this algorithm", "smart-chat"),
        ("Can you verify the patch?", "debug this algorithm", "smart-chat"),
        ("please review this", "debug this algorithm", "smart-chat"),
        ("check the weather", "debug this algorithm", "free-chat"),
        ("handle dinner tonight", "debug this algorithm", "free-chat"),
        ("thanks", "debug this algorithm", "free-chat"),
        ("what's for dinner tonight", "debug this algorithm", "free-chat"),
        ("explain photosynthesis", "debug this algorithm", "free-chat"),
        ("fix dinner", "debug this algorithm", "free-chat"),
        ("add milk to my grocery list", "debug this algorithm", "free-chat"),
    ],
)
def test_route_chat_model_inherits_smart_on_short_followup(
    content: str, prior_user: str | None, expected: str
) -> None:
    assert route_chat_model(content, prior_user=prior_user) == expected


def test_route_chat_model_inherits_smart_from_prior_turn_model() -> None:
    """A follow-up of a follow-up must keep Pro when the last user row stored it.

    Re-scoring ``add tests`` in isolation is Flash, so the next ``fix it``
    would drop off the strong tier without the persisted model.
    """
    assert (
        route_chat_model("fix it", prior_user="add tests", prior_model="smart-chat") == "smart-chat"
    )
    assert route_chat_model("fix it", prior_user="add tests") == "free-chat"


def test_last_user_content_returns_newest_user_line() -> None:
    from types import SimpleNamespace

    from app.services.routing import last_user_content, last_user_turn

    recent = [
        SimpleNamespace(role="user", content="debug this algorithm", model="smart-chat"),
        SimpleNamespace(role="assistant", content="here's a patch"),
        SimpleNamespace(role="user", content=""),
        SimpleNamespace(role="assistant", content="ok"),
    ]
    assert last_user_content(recent) == "debug this algorithm"
    assert last_user_turn(recent) == ("debug this algorithm", "smart-chat")
    assert last_user_content([]) is None
    assert last_user_content(None) is None
    assert last_user_turn([]) == (None, None)


def test_code_fence_detection_is_linear_time_not_quadratic():
    """SECURITY FIX (CodeQL: polynomial regex on uncontrolled data). The
    first version's fence pattern used `\\s*` for leading whitespace, which
    overlaps with what `(?:^|\\n)` already matches — a message that's mostly
    newlines with no closing fence let the engine retry the same run of
    `\\n`s from every line-start position, going quadratic in input length.
    A user-controlled chat message hitting this path is exactly "uncontrolled
    data" — a large adversarial input here must stay fast, not blow up.

    Exercises the compiled pattern directly (not through route_chat_model)
    since route_chat_model short-circuits on the separate long-message
    length check well before an adversarial 200k-char input would ever
    reach the fence regex.
    """
    from app.services.routing import _CODE_FENCE

    # No closing fence anywhere — the worst case for a backtracking engine
    # that overlaps whitespace-skipping with the newline it already matched.
    adversarial = "\n" * 200_000
    started = time.perf_counter()
    _CODE_FENCE.search(adversarial)
    elapsed = time.perf_counter() - started
    # Generous ceiling for a slow CI runner; a quadratic implementation on
    # 200k newlines would take many seconds to minutes, not under a second.
    assert elapsed < 2.0


def test_is_reasoning_alias() -> None:
    from app.services.model_catalog import is_reasoning_alias, quota_multiplier

    assert is_reasoning_alias("smart-chat") is True
    assert is_reasoning_alias("gpt-5.5") is True
    assert is_reasoning_alias("free-chat") is False
    assert quota_multiplier("free-chat") == 1.0
    assert quota_multiplier("smart-chat") == 3.5
    assert quota_multiplier("gpt-5.5") == 3.5


def test_weighted_reserve_tokens_applies_quota_multiplier() -> None:
    from unittest.mock import patch

    from app.core.config import Settings
    from app.services.chat.stream import weighted_reserve_tokens

    settings = Settings()
    with patch("app.services.chat.stream.estimate_tokens", return_value=100):
        free = weighted_reserve_tokens(
            content="hello",
            model="free-chat",
            settings=settings,
            max_output=50,
        )
        smart = weighted_reserve_tokens(
            content="hello",
            model="smart-chat",
            settings=settings,
            max_output=50,
        )
    assert free == 150
    assert smart == 525


def test_prompt_weighted_reserve_tokens_uses_full_prompt() -> None:
    from unittest.mock import patch

    from app.core.config import Settings
    from app.services.chat.stream import prompt_weighted_reserve_tokens

    settings = Settings()
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
    ]
    with patch("app.services.chat.stream.estimate_tokens", return_value=40):
        assert (
            prompt_weighted_reserve_tokens(
                messages,
                model="free-chat",
                settings=settings,
                max_output=20,
            )
            == 100
        )


@pytest.mark.parametrize(
    "alias,content,expected",
    [
        # auto resolves via route_chat_model
        ("auto", "hello", "free-chat"),
        ("auto", "explain gravity", "free-chat"),
        ("auto", "debug this crash", "smart-chat"),
        # explicit aliases pass through
        ("free-chat", "explain gravity", "free-chat"),
        ("smart-chat", "hi", "smart-chat"),
        ("gpt-5.5", "anything", "gpt-5.5"),
    ],
)
def test_resolve_alias(alias: str, content: str, expected: str) -> None:
    assert resolve_alias(alias, content) == expected


def test_auto_hard_question_picks_strongest_when_smart_tier_absent() -> None:
    """Free pool has no smart/max model. Auto used to throw away the
    escalation signal and pick the cheapest fast alias (free-chat). Pick
    the strongest remaining model instead (currently glm-4-flash, standard)."""
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    pool = plan_service.free_pool(settings)
    resolved = resolve_alias_in_pool("auto", "prove p = np", pool, settings)
    assert resolved in pool
    assert model_catalog.tier_rank(model_catalog.get(resolved)) == max(
        model_catalog.tier_rank(model_catalog.get(mid)) for mid in pool
    )
    assert resolved != "free-chat"


def test_pick_smart_from_pool_prefers_strongest_not_cheapest() -> None:
    """When the preferred smart alias is missing, pick strongest remaining smart
    model — not cheapest (glm-5.2 would win on price)."""
    pool = ["glm-5.2", "gpt-5.5"]
    assert routing._pick_smart_from_pool(pool) == "gpt-5.5"
    cheap = model_catalog.price_sort_key(model_catalog.get("glm-5.2"))
    dear = model_catalog.price_sort_key(model_catalog.get("gpt-5.5"))
    assert cheap < dear
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    assert resolve_alias_in_pool("auto", "prove p = np", pool, settings) == "gpt-5.5"


def test_explicit_weak_pick_does_not_escalate() -> None:
    """An explicit picker alias is a promise — even a hard question stays."""
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    pool = ["free-chat", "smart-chat"]
    assert (
        resolve_alias_in_pool(
            "free-chat",
            "prove this algorithm is O(n log n) and derive the recurrence",
            pool,
            settings,
        )
        == "free-chat"
    )
