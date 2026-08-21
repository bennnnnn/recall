"""Import seams for packaged service domains and their compatibility aliases."""

from __future__ import annotations

import importlib


def test_chemistry_service_aliases_canonical_package() -> None:
    legacy = importlib.import_module("app.services.chemistry_service")
    canonical = importlib.import_module("app.services.chemistry")

    assert legacy is canonical
    assert legacy.validate_smiles is canonical.validate_smiles
    assert legacy.balance_equation is canonical.balance_equation
    assert legacy.stoichiometry is canonical.stoichiometry
    assert legacy.molarity is canonical.molarity


def test_chemistry_context_and_fence_alias_canonical_modules() -> None:
    assert importlib.import_module("app.services.chemistry_context") is importlib.import_module(
        "app.services.chemistry.context"
    )
    assert importlib.import_module("app.services.chemistry_fence") is importlib.import_module(
        "app.services.chemistry.fence"
    )


def test_learning_compatibility_modules_share_patchable_module_objects() -> None:
    aliases = {
        "app.services.daily_learning": "app.services.learning.daily",
        "app.services.vocab_quiz": "app.services.learning.quiz",
        "app.services.sm2": "app.services.learning.spaced_repetition",
        "app.services.learning_nudges": "app.services.learning.nudges",
        "app.services.learning_insights": "app.services.learning.insights",
        "app.services.projects.path": "app.services.learning.path",
        "app.services.projects.path_seed": "app.services.learning.path_seed",
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
