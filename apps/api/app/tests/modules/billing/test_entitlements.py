"""Plan policy: one table of what each plan includes, read from config."""

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.models import model_catalog
from app.modules.billing import entitlements, plan
from app.modules.billing.subscription import _plan_from_revenuecat_payload
from app.services import model_health


def _user(plan_id: str) -> SimpleNamespace:
    return SimpleNamespace(plan=plan_id, enabled_models=None)


@pytest.mark.parametrize(
    "plan_id, expected",
    [
        ("free", {"image_generation"}),
        (
            "pro",
            {"all_models", "image_generation", "speech_transcription", "speech_tts", "live_talk"},
        ),
    ],
)
def test_each_plan_includes_exactly_its_features(plan_id, expected):
    assert set(entitlements.features_for(_user(plan_id), Settings())) == expected


def test_live_talk_is_only_on_pro():
    settings = Settings()
    assert [p for p in entitlements.PLANS if entitlements.can_use(p, "live_talk", settings)] == [
        "pro"
    ]


@pytest.mark.parametrize(
    "plan_id, numbers",
    [
        (
            "free",
            {
                "daily_messages": 10,
                "daily_tokens": 400_000,
                "daily_image_generations": 3,
                "daily_speech_transcriptions": 0,
                "daily_speech_tts": 0,
                "monthly_live_talk_minutes": 0,
            },
        ),
        (
            "pro",
            {
                "daily_messages": 1000,
                "daily_tokens": 15_000_000,
                "daily_image_generations": 15,
                "daily_speech_transcriptions": 200,
                "daily_speech_tts": 100,
                "monthly_live_talk_minutes": 60,
            },
        ),
    ],
)
def test_default_numbers_per_plan(plan_id, numbers):
    # The built-in defaults, not a developer's .env overrides.
    settings = Settings(_env_file=None)
    for name, value in numbers.items():
        assert entitlements.allowance(plan_id, name, settings) == value


def test_every_allowance_has_a_setting_for_every_plan():
    fields = Settings.model_fields
    for name in entitlements.ALLOWANCES:
        for plan_id in entitlements.PLANS:
            assert entitlements.setting_name(name, plan_id) in fields


def test_a_feature_moves_between_plans_by_config_alone():
    settings = Settings(daily_speech_tts=20, monthly_live_talk_minutes_pro=0)
    assert entitlements.can_use("free", "speech_tts", settings)
    assert not entitlements.can_use("pro", "live_talk", settings)


# "plus" was a plan until 2026-11-24 (migration 0135 moved its rows to Pro).
@pytest.mark.parametrize("raw", [None, "", "PRO ", "enterprise", "trial", "plus"])
def test_unknown_plans_are_never_paid(raw):
    expected = "pro" if raw == "PRO " else "free"
    assert entitlements.plan_of(raw) == expected


def test_pro_gets_every_model_and_free_gets_the_free_pool():
    settings = Settings(mock_llm_enabled=True, openrouter_api_key="")
    selectable = {
        m.id for m in model_catalog.selectable_models() if model_health.is_available(m, settings)
    }
    assert plan.allowed_model_ids(_user("pro"), settings) == selectable
    assert "smart-chat" not in plan.allowed_model_ids(_user("free"), settings)


def _subscriber(*active: str) -> dict:
    return {
        "subscriber": {
            "entitlements": {
                name: {"expires_date": "2999-01-01T00:00:00Z", "product_identifier": name}
                for name in active
            }
        }
    }


@pytest.mark.parametrize(
    "active, expected",
    [
        ((), "free"),
        # The monthly and the yearly product both grant this one entitlement.
        (("pro",), "pro"),
        # An entitlement the server does not know grants nothing.
        (("plus",), "free"),
        (("plus", "pro"), "pro"),
    ],
)
def test_revenuecat_entitlements_map_to_a_plan(active, expected):
    assert _plan_from_revenuecat_payload(_subscriber(*active), Settings()) == expected


def test_expired_entitlements_do_not_count():
    payload = {
        "subscriber": {
            "entitlements": {
                "pro": {"expires_date": "2001-01-01T00:00:00Z"},
            }
        }
    }
    assert _plan_from_revenuecat_payload(payload, Settings()) == "free"


def test_plan_catalog_lists_exactly_free_and_pro():
    """One paid plan: GET /billing/plans serves this catalog to the paywall."""
    catalog = entitlements.plan_catalog(Settings())
    assert [item["id"] for item in catalog] == ["free", "pro"]
    assert entitlements.PAID_PLANS == frozenset({"pro"})
    pro = catalog[1]
    assert pro["allowances"]["monthly_live_talk_minutes"] == 60
    assert "live_talk" in pro["features"]
