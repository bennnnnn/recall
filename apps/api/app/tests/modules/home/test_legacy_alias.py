"""The legacy Home import path keeps the canonical package surface."""

from app.modules import home as canonical
from app.modules.learning import home_starters as owned_starters
from app.services import home as legacy
from app.services.home import learning_starters as legacy_starters


def test_legacy_home_package_reexports_the_module_surface() -> None:
    assert legacy.invalidate_home_cache is canonical.invalidate_home_cache
    assert legacy.build_home_screen is canonical.build_home_screen
    assert legacy.get_home_screen_cached is canonical.get_home_screen_cached


def test_legacy_learning_starters_follow_learning() -> None:
    assert legacy_starters is owned_starters
    assert legacy_starters.LearningHomeContent is owned_starters.LearningHomeContent
