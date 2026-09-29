"""The legacy Home import path keeps the canonical package surface."""

from app.modules import home as canonical
from app.services import home as legacy


def test_legacy_home_package_reexports_the_module_surface() -> None:
    assert legacy.invalidate_home_cache is canonical.invalidate_home_cache
    assert legacy.build_home_screen is canonical.build_home_screen
    assert legacy.get_home_screen_cached is canonical.get_home_screen_cached
