"""Guards for docs/SUBJECT_SEPARATION_TICKETS.md (S10).

Physics and math share a dispatch layer by design (see
``app.modules.math.tools.extract`` / ``app.modules.math.tools.block`` — both
route on ``MathIntent | PhysicsIntent`` by ``.kind``), but the two subjects'
own kind spaces and internals must not silently re-merge. These tests are the
regression net for that, the same role ``test_domain_package_seams.py`` plays
for the domain-package layout and ``test_physics_prompt_boundary.py`` plays for
solver-coverage vs. prompt claims: cheap, structural, and they name the file
and the fix when they fail instead of leaving the next reader to rediscover
the separation by hand.
"""

from __future__ import annotations

import ast
import typing
from pathlib import Path

import pytest

from app.models.schemas.math import MathIntent
from app.models.schemas.physics import PhysicsIntent

_PHYSICS_DIR = Path(__file__).resolve().parents[2] / "modules" / "physics"

# Every remaining import of physics FROM math, named explicitly. A new entry
# here is a review question — is this a genuinely shared primitive
# (GraphBlockSpec: physics trajectories reuse math's own graph fence type) or
# intentional public cross-subject API (get_unit_registry,
# extract_average_speed_intent: both dropped their leading underscore in S3
# specifically so this dependency would be visible and named, not a new
# private reach-in) — not a silent, unreviewed reopening of the fusion S2-S4
# closed. MathIntent itself is allowed once, for the one legitimate union
# case: average speed is a math kind (arithmetic) that physics's direct-reply
# path cross-checks against, not a physics kind.
_ALLOWED_MATH_IMPORTS: frozenset[tuple[str, str]] = frozenset(
    {
        ("app.models.schemas.math", "MathIntent"),
        ("app.models.schemas.math", "GraphBlockSpec"),
        ("app.modules.math", "extract_average_speed_intent"),
        ("app.modules.math", "get_unit_registry"),
    }
)


def _math_imports(tree: ast.Module) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        if not (
            node.module == "app.modules.math"
            or node.module.startswith("app.modules.math.")
            or node.module == "app.models.schemas.math"
            or node.module.startswith("app.models.schemas.math.")
        ):
            continue
        for alias in node.names:
            found.add((node.module, alias.name))
    return found


def test_legacy_physics_submodule_is_the_canonical_module() -> None:
    import app.services.physics.numbers as legacy

    import app.modules.physics.numbers as canonical

    assert legacy is canonical


def test_physics_imports_from_math_are_allowlisted() -> None:
    """A new import here must be named in `_ALLOWED_MATH_IMPORTS`, not silent."""
    offenders: dict[str, set[tuple[str, str]]] = {}
    for path in sorted(_PHYSICS_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        unexpected = _math_imports(tree) - _ALLOWED_MATH_IMPORTS
        if unexpected:
            offenders[path.name] = unexpected
    assert not offenders, (
        f"modules/physics/ imports from math outside the allowlist: {offenders}. "
        "If this is intentional, add it to _ALLOWED_MATH_IMPORTS with a reason; "
        "if it is a private (`_`-prefixed) name, expose a public one instead "
        "(see docs/SUBJECT_SEPARATION_TICKETS.md, S3)."
    )


def test_math_and_physics_intent_kinds_are_disjoint() -> None:
    """The type split's actual point: two closed kind spaces, not one shared enum.

    A kind added to either Literal that also exists on the other would dispatch
    to whichever registry happens to be checked first in
    `math/tools/block/__init__.py` — silently, since both are valid `str` keys
    to the `_BLOCK_BUILDERS` dict lookup that routes on `.kind`.
    """
    math_kinds = set(typing.get_args(MathIntent.model_fields["kind"].annotation))
    physics_kinds = set(typing.get_args(PhysicsIntent.model_fields["kind"].annotation))
    assert math_kinds & physics_kinds == set()


def test_physics_intent_kind_count_matches_the_verified_registry() -> None:
    """Twenty kinds, per docs/PHYSICS_TICKETS_ROUND3.md — pinned so a kind added
    to one without the other (the enum or PHYSICS_BLOCK_BUILDERS) is caught here
    rather than by a silent dispatch miss in production."""
    from app.modules.physics.block import PHYSICS_BLOCK_BUILDERS

    physics_kinds = set(typing.get_args(PhysicsIntent.model_fields["kind"].annotation))
    assert physics_kinds == set(PHYSICS_BLOCK_BUILDERS)
    assert len(physics_kinds) == 20


@pytest.mark.parametrize(
    "module",
    [
        "app.services.solving",
        "app.services.text_match",
        "app.models.schemas.physics",
        "app.models.schemas.physics.intent",
        "app.models.schemas.physics.simulation",
    ],
)
def test_new_subject_neutral_modules_import_cold_in_isolation(module: str) -> None:
    """`app.services.solving` sits in a real cycle: `math.solve` imports
    `MathServiceError` from it, and it type-only-imports back into
    `math.solve.key_steps`. A real (non-TYPE_CHECKING) import there would only
    fail on a cold interpreter where neither side is already cached — the same
    class of bug `test_physics_modules_import_cold_in_isolation` guards for
    physics/math. See docs/SUBJECT_SEPARATION_TICKETS.md, S2.
    """
    import subprocess
    import sys

    result = subprocess.run(  # noqa: S603 - fixed argv, module names are literals above
        [sys.executable, "-c", f"import {module}"], capture_output=True, text=True
    )
    assert result.returncode == 0, f"{module} failed to import cold:\n{result.stderr}"
