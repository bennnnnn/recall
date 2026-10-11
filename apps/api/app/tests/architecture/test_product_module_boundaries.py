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


def test_chat_runtime_code_has_one_owner() -> None:
    """History, both transports, turn prep and the stream pipeline are one module."""
    module_root = APP_ROOT / "modules" / "chat"
    expected = {
        "api.py",
        "post_turn.py",
        "prompt_builder.py",
        "service.py",
        "stream.py",
        "stream_api.py",
        "stream_entry.py",
        "stream_events.py",
        "stream_pipeline.py",
        "ws_api.py",
    }
    assert (module_root / "turn_prep" / "prepare.py").is_file()
    assert (module_root / "prompt_constants" / "__init__.py").is_file()
    assert not (APP_ROOT / "services" / "chat").exists()
    assert {"test_ws.py", "test_chat_stream.py", "test_turn_prep_parallel.py"} <= {
        path.name for path in (APP_ROOT / "tests" / "modules" / "chat").glob("*.py")
    }
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert {
        "test_chat_management.py",
        "test_chat_history_recovery.py",
    } <= {path.name for path in (APP_ROOT / "tests" / "modules" / "chat").glob("*.py")}


def test_account_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "account"
    expected = {
        "api.py",
        "export.py",
        "lifecycle.py",
        "profile.py",
        "service.py",
        "settings_intent.py",
        "settings_proposal.py",
        "tokens.py",
        "web_session.py",
    }
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert {"test_account.py", "test_tokens.py", "test_web_session.py"} <= {
        path.name for path in (APP_ROOT / "tests" / "modules" / "account").glob("*.py")
    }
    # Every request verifies its token in core; core never imports the module.
    assert (APP_ROOT / "core" / "access_tokens.py").is_file()
    assert (APP_ROOT / "modules" / "notifications" / "api.py").is_file()


def test_mobile_account_and_auth_have_feature_homes() -> None:
    """Sign-in and settings screens live in features/; their routes only map URLs."""
    routes = {
        "app/login.tsx": "features/auth/screens/LoginScreen",
        "app/onboarding.tsx": "features/auth/screens/OnboardingScreen",
        "app/settings/index.tsx": "features/account/screens/SettingsScreen",
        "app/settings/preferences.tsx": "features/account/screens/PreferencesSettingsScreen",
        "app/settings/notifications.tsx": "features/account/screens/NotificationsSettingsScreen",
        "app/settings/data-controls.tsx": "features/account/screens/DataControlsScreen",
        "app/settings/security.tsx": "features/account/screens/SecuritySettingsScreen",
        "app/settings/archived-chats.tsx": "features/account/screens/ArchivedChatsScreen",
        "app/settings/models.tsx": "features/account/screens/ModelsSettingsScreen",
        "app/settings/usage.tsx": "features/account/screens/UsageSettingsScreen",
        "app/settings/about.tsx": "features/account/screens/AboutScreen",
        "app/settings/help.tsx": "features/account/screens/HelpSettingsScreen",
    }
    for route, screen in routes.items():
        lines = [line for line in (MOBILE_ROOT / route).read_text().splitlines() if line.strip()]
        assert lines == [f'export {{ default }} from "@/{screen}";'], route
        assert (MOBILE_ROOT / f"{screen}.tsx").is_file(), screen
    for feature in ("account", "auth"):
        root = MOBILE_ROOT / "features" / feature
        assert (root / "api.ts").is_file()
        violations = [
            str(path.relative_to(MOBILE_ROOT))
            for path in root.rglob("*.ts*")
            if "__tests__" not in path.parts and "@/app/" in path.read_text()
        ]
        assert not violations
    for gone in (
        "components/settings",
        "components/settings/AccountSettingsSection.tsx",
        "components/settings/AppearanceSettingsRow.tsx",
        "components/settings/ConnectedAppCard.tsx",
        "components/settings/EditableProfileAvatar.tsx",
        "components/settings/SettingsFieldSheet.tsx",
        "components/settings/SettingsOverview.tsx",
        "components/settings/SettingsPickerSheet.tsx",
        "components/settings/SettingsProfile.tsx",
        "components/settings/SettingsProfileSheet.tsx",
        "components/settings/SettingsSkeleton.tsx",
        "components/settings/settingsStyles.ts",
        "components/settings/settingsUi.tsx",
        "hooks/useDataControls.ts",
        "hooks/useLoginActions.ts",
        "hooks/useProfileEditor.ts",
        "hooks/usePushNotificationToggle.ts",
        "hooks/useUsage.ts",
        "lib/api/account.ts",
        "lib/api/auth.ts",
    ):
        assert not (MOBILE_ROOT / gone).exists(), gone


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

    # A submodule the owner declares public may be imported by path, nested or not.
    declared = ast.parse(
        "from app.modules.attachments.markers import strip_attachment_from_content\n"
        "from app.modules.math.tools.extract import is_graph_followup\n"
    )
    assert not _foreign_module_import_violations(declared, owner="chat", label="sample")
    undeclared = ast.parse("from app.modules.math.tools.block import build_block\n")
    assert _foreign_module_import_violations(undeclared, owner="chat", label="sample") == [
        "sample imports app.modules.math.tools.block"
    ]


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
