"""Tests for chat model routing (``modules/chat/model_routing``): pure functions, no I/O."""

import time
from typing import Any

import pytest

from app.core.config import Settings
from app.models import model_catalog
from app.modules.billing import plan
from app.modules.billing import plan as plan_service
from app.modules.chat.model_routing.route import (
    message_needs_thinking,
    resolve_alias_in_pool,
    route_chat_model,
    routed_chat_model,
)
from app.modules.physics import lane as routing_physics

# Auto's maths lane, whichever model runs it (``ROUTING.math``).
_MATH = model_catalog.auto_math_alias()


@pytest.mark.parametrize(
    "content,expected",
    [
        # Simple messages → the fast auto alias (Gemini Flash).
        ("hi", "hy4-flash"),
        ("hello world", "hy4-flash"),
        ("what's for lunch", "hy4-flash"),
        ("explain quantum computing", "hy4-flash"),
        ("why is the sky blue", "hy4-flash"),
        ("compare two options", "hy4-flash"),
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
        # Tutoring has a strict format/state contract and uses the low-latency
        # teaching lane; live QA showed the reasoning tier added 10-20s TTFT.
        ("Teach me python dictionaries", "hy4-flash"),
        ("Teach me python dictionaries step by step", "hy4-flash"),
        ("Help me learn SQL joins", "hy4-flash"),
        ("Give me a 70-day Python mastery plan", "hy4-flash"),
        ("70 days mastering python from beginner to senior level plan", "hy4-flash"),
        ("Create a 70-day Python plan", "hy4-flash"),
        ("70-day roadmap for Python", "hy4-flash"),
        ("Give me a daily Python curriculum for 70 days", "hy4-flash"),
        ("Teach me Python over the next 70 days", "hy4-flash"),
        # Ordinary non-learning plans stay fast.
        ("Give me a 30-day workout plan", "hy4-flash"),
        ("Create a 12-week business plan", "hy4-flash"),
        (
            "Create a 4-column markdown table with a Main tradeoff column, then show a code block",
            "hy4-flash",
        ),
        ("I studied Python for 70 days and now plan to apply for jobs", "hy4-flash"),
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
        ("a" * 799, "hy4-flash"),
        # Any code fence → smart-chat, regardless of language tag (or lack of
        # one). BUG FIX: this used to only match a fixed language allowlist,
        # so a bare fence or an unlisted language (bash, shell, C, HTML, ...)
        # silently stayed on free-chat even with real pasted code.
        ("check this:\n```python\nprint(1)\n```", "smart-chat"),
        ("check this out:\n```\nprint(1)\n```", "smart-chat"),
        ("run this:\n```bash\necho hi\n```", "smart-chat"),
        ("what's wrong here:\n```html\n<div></div>\n```", "smart-chat"),
        # Math / structured turns → the maths lane (a weak fast model disagreed with
        # verified results; measured 2026-11-10).
        ("solve 2x + 3 = 7", _MATH),
        ("graph y = x^2", _MATH),
        ("2x+3=7", _MATH),
        ("find the area of a circle radius 4", _MATH),
        ("integrate x^2 from 0 to 1", _MATH),
        ("standard deviation of 1, 2, 3, 4, 5", _MATH),
        # Verified closed-form arithmetic stays free-chat — R1 used to dump a
        # live Reasoning essay ("the user just wrote 4!") on these.
        ("4!", "hy4-flash"),
        ("what is 1+1", "hy4-flash"),
        ("3+0", "hy4-flash"),
        ("3 + 0", "hy4-flash"),
        ("7*8", "hy4-flash"),
        ("8-8*2", "hy4-flash"),
        # Arithmetic next to a hard question is not a fast-path whole message.
        ("what is 1+1 and also graph y = x^2", _MATH),
        # A recognized physics template stays on the fast model; the verifier
        # owns the number. Homework the templates miss still goes to smart-chat.
        (
            "a 2kg block slides down a 30° frictionless incline, find its acceleration",
            "hy4-flash",
        ),
        ("calculate the momentum of a 5kg object moving at 12 m/s", "hy4-flash"),
        ("what is the escape velocity of earth", "hy4-flash"),
        ("a ball is dropped from 20 m, how long to hit the ground", "hy4-flash"),
        ("equations of motion for a pendulum", "smart-chat"),
        (
            "a block slides down a 90° frictionless incline, find its acceleration",
            "smart-chat",
        ),
        ("physics", "hy4-flash"),
        ("the project has momentum now", "hy4-flash"),
        # Plain prose with no math cue stays on the fast alias.
        ("what's for dinner tonight", "hy4-flash"),
        ("What is a Python list?", "hy4-flash"),
        ("thanks, that helped", "hy4-flash"),
        # Hard reasoning with no trigger word (R4.3).
        (
            "plan a zero-downtime migration of a monolith Postgres schema to sharded tables",
            "smart-chat",
        ),
        (
            "All cats are mammals. Some mammals are black. Does it follow that some cats "
            "are black? Explain carefully.",
            "smart-chat",
        ),
        ("plan my week", "hy4-flash"),
        ("drive carefully, it's icy", "hy4-flash"),
        # Code review and code writing with no fence (R4.6).
        (
            "can you review my function that reverses a linked list, it keeps looping forever",
            "smart-chat",
        ),
        ("write a python function to reverse a string", "smart-chat"),
        ("can you review my cover letter", "hy4-flash"),
        ("my promo code doesn't work", "hy4-flash"),
        # Pasted data under 800 characters (R4.8).
        (
            'find the duplicate ids: [{"id": 4, "name": "Ana"}, {"id": 9, "name": "Ben"}, '
            '{"id": 4, "name": "Cy"}, {"id": 12, "name": "Di"}, {"id": 9, "name": "Ed"}, '
            '{"id": 15, "name": "Flo"}, {"id": 21, "name": "Gus"}, {"id": 15, "name": "Hal"}]',
            "smart-chat",
        ),
        ("my scores were [90, 85, 77], is that good?", "hy4-flash"),
        # A matrix stays on the maths lane; writing about a migration stays everyday.
        ("determinant of [[1,2,3],[0,1,4],[5,6,0]]", _MATH),
        (
            "write a tweet announcing that we finished migrating our whole backend to "
            "postgres, zero downtime",
            "hy4-flash",
        ),
    ],
)
def test_route_chat_model(content: str, expected: str) -> None:
    assert route_chat_model(content) == expected


@pytest.mark.parametrize(
    "content,prior_user,expected",
    [
        ("What would be the solution if the equation were 3x^2 + 5 = 8?", None, False),
        ("what's for dinner tonight", None, False),
        ("prove the quadratic formula", None, True),
        ("debug this algorithm", None, True),
        ("why", "prove the quadratic formula", True),
        ("why", "What would be the solution if the equation were 3x^2 + 5 = 8?", False),
    ],
)
def test_message_needs_thinking(content: str, prior_user: str | None, expected: bool) -> None:
    assert message_needs_thinking(content, prior_user=prior_user) is expected


def test_verified_physics_stays_smart_when_physics_is_off() -> None:
    content = "calculate the momentum of a 5kg object moving at 12 m/s"
    pool = [model.id for model in model_catalog.selectable_models()]
    assert (
        resolve_alias_in_pool(
            "auto",
            content,
            pool,
            Settings(physics_enabled=False),
        )
        == "smart-chat"
    )


@pytest.mark.parametrize(
    "content,prior_user,expected",
    [
        ("Now fix it", None, "hy4-flash"),
        ("Now fix it", "debug this algorithm", "smart-chat"),
        ("add tests", "debug this algorithm", "smart-chat"),
        ("check if it is fixed", "debug this algorithm", "smart-chat"),
        ("Handle the edge cases", "debug this algorithm", "smart-chat"),
        ("Can you verify the patch?", "debug this algorithm", "smart-chat"),
        ("please review this", "debug this algorithm", "smart-chat"),
        ("check the weather", "debug this algorithm", "hy4-flash"),
        ("handle dinner tonight", "debug this algorithm", "hy4-flash"),
        ("thanks", "debug this algorithm", "hy4-flash"),
        ("what's for dinner tonight", "debug this algorithm", "hy4-flash"),
        ("explain photosynthesis", "debug this algorithm", "hy4-flash"),
        ("fix dinner", "debug this algorithm", "hy4-flash"),
        ("add milk to my grocery list", "debug this algorithm", "hy4-flash"),
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
    assert route_chat_model("fix it", prior_user="add tests") == "hy4-flash"


def test_route_chat_model_keeps_math_followup_on_low_latency_strong_model() -> None:
    prior = "solve 3x^2 + x^0 = 3"
    assert routed_chat_model("how?", prior_user=prior) == (_MATH, "inherit_math")
    assert routed_chat_model("Why is x = -1 rejected?", prior_user=prior)[0] == _MATH
    assert routed_chat_model("How did you factor that?", prior_user=prior)[0] == _MATH
    assert (
        route_chat_model("show the next step", prior_user="try again", prior_model=_MATH) == _MATH
    )


def test_a_follow_up_of_a_hard_turn_on_the_strong_model_is_no_maths() -> None:
    """With the maths lane on the strong lane's model, a code follow-up after a code turn
    inherits the strong lane as code, not as maths: maths would think less."""
    route = routed_chat_model(
        "now make it handle empty lists",
        prior_user="write a python function that averages a list",
        prior_model=model_catalog.auto_smart_alias(),
    )
    assert route == (model_catalog.auto_smart_alias(), "inherit_smart")


@pytest.mark.parametrize(
    "reaction",
    ["A", "red", "I'm confused", "why?", "next", "Bad bdbd head hdjjd jdjdd"],
)
def test_route_chat_model_keeps_active_tutor_turns_on_low_latency_lane(reaction: str) -> None:
    assert route_chat_model(reaction, lesson_active=True) == "hy4-flash"


def test_route_chat_model_does_not_treat_short_text_as_a_lesson_without_state() -> None:
    assert route_chat_model("red") == "hy4-flash"


def test_last_user_turn_returns_newest_user_line() -> None:
    from types import SimpleNamespace

    from app.modules.chat.model_routing.route import last_user_turn

    recent = [
        SimpleNamespace(role="user", content="debug this algorithm", model="smart-chat"),
        SimpleNamespace(role="assistant", content="here's a patch"),
        SimpleNamespace(role="user", content=""),
        SimpleNamespace(role="assistant", content="ok"),
    ]
    assert last_user_turn(recent) == ("debug this algorithm", "smart-chat")
    assert last_user_turn([]) == (None, None)


@pytest.mark.wall_clock
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
    from app.modules.chat.model_routing.route import _CODE_FENCE

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
    from app.models.model_catalog import is_reasoning_alias, quota_multiplier

    assert is_reasoning_alias("smart-chat") is True
    assert is_reasoning_alias("qwen-3.8-flash") is True
    assert is_reasoning_alias("free-chat") is False
    assert quota_multiplier("free-chat") == 1.0
    assert quota_multiplier("smart-chat") == 3.5
    assert quota_multiplier("qwen-3.8-flash") == 3.5


def test_weighted_reserve_tokens_applies_quota_multiplier() -> None:
    from unittest.mock import patch

    from app.core.config import Settings
    from app.modules.chat.turn_resources import weighted_reserve_tokens

    settings = Settings()
    with patch("app.modules.chat.turn_resources.estimate_tokens", return_value=100):
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
    from app.modules.chat.turn_resources import prompt_weighted_reserve_tokens

    settings = Settings()
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
    ]
    with patch("app.modules.chat.turn_resources.estimate_tokens", return_value=40):
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
        ("auto", "hello", "hy4-flash"),
        ("auto", "explain gravity", "hy4-flash"),
        ("auto", "debug this crash", "smart-chat"),
        # explicit aliases pass through
        ("free-chat", "explain gravity", "free-chat"),
        ("smart-chat", "hi", "smart-chat"),
        ("gpt-6-luna", "anything", "gpt-6-luna"),
    ],
)
def test_resolve_alias(alias: str, content: str, expected: str) -> None:
    pool = [model.id for model in model_catalog.selectable_models()]
    assert resolve_alias_in_pool(alias, content, pool) == expected


def test_auto_hard_question_picks_strongest_when_smart_tier_absent() -> None:
    """Free pool has no smart/max model. Auto used to throw away the
    escalation signal and pick the cheapest fast alias (free-chat). Pick
    the strongest remaining model instead (currently glm-5.3-flash, standard)."""
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    pool = plan_service.free_pool(settings)
    resolved = resolve_alias_in_pool("auto", "prove p = np", pool, settings)
    assert resolved in pool
    assert model_catalog.tier_rank(model_catalog.get(resolved)) == max(
        model_catalog.tier_rank(model_catalog.get(mid)) for mid in pool
    )
    assert resolved != "free-chat"


def test_pick_smart_from_pool_prefers_strongest_not_cheapest() -> None:
    """With several smart models, pick the strongest (the dearest), not the cheapest
    (Qwen3.8 Flash would win on price)."""
    pool = ["qwen-3.8-flash", "smart-chat"]
    assert plan.pick_smart_from_pool(pool) == "smart-chat"
    cheap = model_catalog.price_sort_key(model_catalog.get("qwen-3.8-flash"))
    dear = model_catalog.price_sort_key(model_catalog.get("smart-chat"))
    assert cheap < dear


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


_VERIFIED_PHYSICS = "calculate the momentum of a 5kg object moving at 12 m/s"


def test_physics_route_declines_when_the_solver_raises(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A solver bug is a decline to the strong model, never a failed turn."""
    import app.modules.physics.prompt as physics_prompt

    def broken(*_args: object) -> object:
        raise ZeroDivisionError("solver bug")

    monkeypatch.setattr(physics_prompt, "solve_physics_request", broken)
    routing_physics._physics_solves.cache_clear()
    try:
        assert route_chat_model(_VERIFIED_PHYSICS) == "smart-chat"
    finally:
        routing_physics._physics_solves.cache_clear()
    assert "physics routing solve failed" in caplog.text


def test_physics_route_solves_each_line_once(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.modules.physics.prompt as physics_prompt

    calls = 0
    real = physics_prompt.solve_physics_request

    def counting(*args: Any) -> Any:
        nonlocal calls
        calls += 1
        return real(*args)

    monkeypatch.setattr(physics_prompt, "solve_physics_request", counting)
    routing_physics._physics_solves.cache_clear()
    try:
        for _ in range(3):
            assert route_chat_model(_VERIFIED_PHYSICS) == "hy4-flash"
            assert (
                route_chat_model(
                    "and its kinetic energy?",
                    prior_user=_VERIFIED_PHYSICS,
                    prior_model="smart-chat",
                )
                is not None
            )
    finally:
        routing_physics._physics_solves.cache_clear()
    assert calls == 1


@pytest.mark.parametrize(
    "question",
    [
        # The phys30 round (2026-11-16): the read was late and these went to the everyday
        # model, thinking off; the slope's range came back 26.0 m for 16.7 m.
        "A ball is launched with speed 15 m/s at 50 degrees above the horizontal from the "
        "bottom of a hill that slopes upward at 20 degrees to the horizontal. (a) How long is "
        "the ball in the air? (b) How far up along the slope does it land?",
        "A 2 kg block is dropped from 0.5 m above a spring of constant 1000 N/m. (a) What is "
        "its speed when it reaches the spring? (b) What is the maximum compression?",
        # A question in parts the template answers one of: the strong model answers it.
        "A curve of radius 80 m is banked at 15 degrees. (a) At what speed can a car take the "
        "curve with no friction needed? (b) If the coefficient of static friction between the "
        "tyres and the road is 0.4, what is the maximum speed at which the car can take the "
        "curve without sliding?",
    ],
)
def test_physics_the_subject_order_reads_keeps_the_strong_lane(question: str) -> None:
    routing_physics._physics_solves.cache_clear()
    assert routed_chat_model(question) == ("smart-chat", "physics")
    assert message_needs_thinking(question)


@pytest.mark.parametrize(
    "line",
    [
        # Rate and unit words the order gives physics, read as no problem: the everyday
        # model, as before (review of phys30, 2026-11-16).
        "How long does it take to drive 10 km to the airport from my location?",
        "How far is the nearest gas station? My car does 30 mpg",
        "my battery went from 100% to 25% in 3 hours, how long until it's empty at that rate?",
        "a reminder: the tank fills at 3 L/min and holds 240 L. there's already 60 L in it. "
        "how long until it's full?",
        # A card payoff is the money card's, never physics' lane.
        "I have $5,000 on my credit card at 22% APR and pay $200 a month. How long until "
        "it's paid off?",
    ],
)
def test_a_line_physics_only_claims_by_its_words_keeps_the_everyday_lane(line: str) -> None:
    routing_physics._physics_solves.cache_clear()
    assert routed_chat_model(line) == ("hy4-flash", "everyday")
