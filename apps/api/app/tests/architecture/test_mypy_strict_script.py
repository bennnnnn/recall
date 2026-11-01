"""The strict ratchet lets a package go only when an override really holds all of it."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[5] / "scripts" / "check_mypy_strict.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_mypy_strict", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pyproject(modules: list[str], *, flags: tuple[str, ...]) -> str:
    listed = ", ".join(f'"{module}"' for module in modules)
    lines = [f"{flag} = true" for flag in flags]
    return "[tool.mypy]\n\n[[tool.mypy.overrides]]\nmodule = [" + listed + "]\n" + "\n".join(lines)


@pytest.mark.parametrize(
    ("modules", "drop_flag", "held"),
    [
        (["app.modules.physics", "app.modules.physics.*"], None, True),
        # 2026-11-01: listing the package alone held only its __init__, yet left the ratchet.
        (["app.modules.physics"], None, False),
        (["app.modules.physics.*"], None, False),
        (["app.modules.physics", "app.modules.physics.*"], "warn_return_any", False),
    ],
)
def test_a_package_leaves_the_ratchet_only_when_wholly_strict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    modules: list[str],
    drop_flag: str | None,
    held: bool,
) -> None:
    script = _load()
    flags = tuple(flag for flag in script.STRICT_FLAGS if flag != drop_flag)
    (tmp_path / "pyproject.toml").write_text(_pyproject(modules, flags=flags))
    monkeypatch.setattr(script, "API", tmp_path)
    assert ("app.modules.physics" in script.strict_packages()) is held
    assert ("app.modules.physics" in script.ratcheted()) is not held
