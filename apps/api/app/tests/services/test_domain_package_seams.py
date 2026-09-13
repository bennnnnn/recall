"""Import seams for packaged service domains and their compatibility aliases."""

from __future__ import annotations

import importlib

import pytest

# Flat `services/<domain>_<thing>.py` modules that were folded into a domain
# package. The compatibility aliases are gone; importing the old name must fail
# so a future edit cannot quietly reintroduce the split-brain layout.
RETIRED_FLAT_MODULES = (
    "app.services.chemistry_service",
    "app.services.chemistry_context",
    "app.services.chemistry_fence",
)


@pytest.mark.parametrize("legacy_name", RETIRED_FLAT_MODULES)
def test_retired_flat_modules_are_gone(legacy_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(legacy_name)


def test_chemistry_package_exposes_its_public_api() -> None:
    chemistry = importlib.import_module("app.services.chemistry")

    assert callable(chemistry.validate_smiles)
    assert callable(chemistry.balance_equation)
    assert callable(chemistry.stoichiometry)
    assert callable(chemistry.molarity)
    assert callable(
        importlib.import_module("app.services.chemistry.context").build_chemistry_context
    )
    assert callable(importlib.import_module("app.services.chemistry.fence").enrich_chemistry_fences)


def test_learning_compatibility_modules_share_patchable_module_objects() -> None:
    aliases = {
        "app.services.daily_learning": "app.services.learning.daily",
        "app.services.sm2": "app.services.learning.spaced_repetition",
    }

    for legacy_name, canonical_name in aliases.items():
        assert importlib.import_module(legacy_name) is importlib.import_module(canonical_name)


def test_notification_compatibility_modules_share_patchable_module_objects() -> None:
    aliases = {
        "app.services.push_notifications": "app.services.notifications.push",
        "app.services.transactional_email": "app.services.notifications.transactional_email",
        "app.services.reminder_emails": "app.services.notifications.reminder_email",
    }

    for legacy_name, canonical_name in aliases.items():
        assert importlib.import_module(legacy_name) is importlib.import_module(canonical_name)


def test_math_extraction_public_seam_uses_focused_extractors() -> None:
    extract = importlib.import_module("app.services.math_tools.extract")

    assert extract.extract_math_intent("solve x + 2 = 5").kind == "equation"
    assert extract.extract_math_intent("draw a square with side 4").kind == "square"
    assert extract.extract_math_intent("differentiate x^2").kind == "calculus"
    assert extract.extract_math_intent("mean of 1, 2, 3").kind == "statistics"
