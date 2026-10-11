"""Ownership checks for subjects, billing, notifications, home, search, and chat."""

import ast

from .boundary_support import (
    APP_ROOT,
    MOBILE_ROOT,
    _foreign_module_import_violations,
)


def test_chemistry_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "chemistry"
    expected = {
        "block.py",
        "context.py",
        "direct.py",
        "equations.py",
        "extract.py",
        "fence.py",
        "request.py",
        "smiles.py",
        "stoichiometry.py",
    }
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (module_root / "solvers" / "solver.py").is_file()
    assert (APP_ROOT / "tests" / "modules" / "chemistry" / "test_chemistry_service.py").is_file()
    assert not (MOBILE_ROOT / "features" / "chemistry").exists()
    assert (MOBILE_ROOT / "lib" / "chemistry" / "fence.ts").is_file()


def test_physics_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "physics"
    expected = {"block.py", "direct.py", "extract.py", "request.py", "solver.py"}
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (module_root / "extractors").is_dir()
    assert (module_root / "solvers").is_dir()
    assert (APP_ROOT / "tests" / "modules" / "physics" / "test_physics_solver.py").is_file()


def test_math_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "math"
    expected = {"fence.py", "school.py", "sympy_warmup.py", "tool.py"}
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (module_root / "match").is_dir()
    assert (module_root / "tools").is_dir()
    assert (module_root / "solve").is_dir()
    assert (APP_ROOT / "tests" / "modules" / "math" / "test_math_service.py").is_file()


def test_billing_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "billing"
    expected = {"api.py", "plan.py", "revenuecat.py", "subscription.py"}
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (APP_ROOT / "tests" / "services" / "test_plan.py").is_file()


def test_notifications_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "notifications"
    expected = {"push.py", "reminder_email.py", "transactional_email.py"}
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (APP_ROOT / "tests" / "services" / "test_push_notifications.py").is_file()


def test_home_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "home"
    expected = {
        "api.py",
        "memory_starters.py",
        "time_starters.py",
        "util.py",
    }
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (APP_ROOT / "tests" / "modules" / "home" / "test_service.py").is_file()


def test_suggestions_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "suggestions"
    expected = {"api.py", "models.py", "repository.py", "service.py"}
    assert expected <= {path.name for path in module_root.glob("*.py")}


def test_search_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "search"
    expected = {"api.py", "repository.py", "service.py"}
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert {
        "test_api.py",
        "test_query.py",
        "test_repository.py",
        "test_repository_db.py",
    } <= {path.name for path in (APP_ROOT / "tests" / "modules" / "search").glob("*.py")}


def test_chat_history_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "chat"
    expected = {"api.py", "service.py"}
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert {
        "test_chat_management.py",
        "test_chat_history_recovery.py",
    } <= {path.name for path in (APP_ROOT / "tests" / "modules" / "chat").glob("*.py")}


def test_mobile_home_has_one_feature_home() -> None:
    feature_root = MOBILE_ROOT / "features" / "home"
    assert (feature_root / "api.ts").is_file()
    for folder in ("components", "context", "model"):
        assert (feature_root / folder).is_dir()

    assert not (MOBILE_ROOT / "components" / "HomeStarters.tsx").exists()
    assert not (MOBILE_ROOT / "contexts" / "HomeContext.tsx").exists()
    assert not (MOBILE_ROOT / "lib" / "homeWelcome.ts").exists()
    assert not (MOBILE_ROOT / "lib" / "homeGuidancePrefs.ts").exists()
    assert "getHomeScreen" not in (MOBILE_ROOT / "lib" / "api" / "discover.ts").read_text()

    feature_import_violations = [
        str(path.relative_to(MOBILE_ROOT))
        for path in feature_root.rglob("*.ts*")
        if "__tests__" not in path.parts and "@/app/" in path.read_text()
    ]
    assert not feature_import_violations


def test_mobile_search_has_one_feature_home() -> None:
    feature_root = MOBILE_ROOT / "features" / "search"
    assert (feature_root / "api.ts").is_file()
    for folder in ("components", "hooks", "model"):
        assert (feature_root / folder).is_dir()

    assert not (MOBILE_ROOT / "hooks" / "useDrawerSearch.ts").exists()
    assert not (MOBILE_ROOT / "lib" / "drawerSearchLogic.ts").exists()
    assert not (MOBILE_ROOT / "components" / "drawer" / "DrawerSearchResults.tsx").exists()
    assert "search:" not in (MOBILE_ROOT / "lib" / "api" / "discover.ts").read_text()

    feature_import_violations = [
        str(path.relative_to(MOBILE_ROOT))
        for path in feature_root.rglob("*.ts*")
        if "__tests__" not in path.parts and "@/app/" in path.read_text()
    ]
    assert not feature_import_violations


def test_mobile_suggestions_has_one_feature_home() -> None:
    feature_root = MOBILE_ROOT / "features" / "suggestions"
    assert (feature_root / "api.ts").is_file()
    for folder in ("components", "hooks"):
        assert (feature_root / folder).is_dir()

    assert not (MOBILE_ROOT / "hooks" / "useChatSuggestions.ts").exists()
    assert not (MOBILE_ROOT / "components" / "SuggestionChips.tsx").exists()
    discover = (MOBILE_ROOT / "lib" / "api" / "discover.ts").read_text()
    assert "listSuggestions" not in discover
    assert "dismissSuggestion" not in discover

    feature_import_violations = [
        str(path.relative_to(MOBILE_ROOT))
        for path in feature_root.rglob("*.ts*")
        if "__tests__" not in path.parts and "@/app/" in path.read_text()
    ]
    assert not feature_import_violations


def test_web_search_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "web_search"
    expected = {"augment.py", "detection.py", "formatting.py", "search_cache.py", "tool.py"}
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (APP_ROOT / "tests" / "modules" / "web_search" / "test_web_search.py").is_file()


def test_package_import_cannot_pull_a_private_name() -> None:
    leaked = ast.parse("from app.modules.attachments import repository\n")
    violations = _foreign_module_import_violations(leaked, owner="images", label="sample")
    assert violations == ["sample imports repository from app.modules.attachments"]

    public = ast.parse(
        "from app.modules.attachments import service\n"
        "from app.modules.todos import snap_first_due\n"
        "from app.modules.todos import repository\n"
        "from app.modules.integrations import calendar\n"
    )
    assert not _foreign_module_import_violations(public, owner="images", label="sample")


def test_modules_import_other_modules_only_through_public_files() -> None:
    """Another product module may use a public file or an exported package name."""
    violations: list[str] = []
    modules_root = APP_ROOT / "modules"
    for path in modules_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        owner = path.relative_to(modules_root).parts[0]
        tree = ast.parse(path.read_text(), filename=str(path))
        violations.extend(
            _foreign_module_import_violations(
                tree, owner=owner, label=str(path.relative_to(APP_ROOT))
            )
        )
    assert not violations, "\n".join(violations)
