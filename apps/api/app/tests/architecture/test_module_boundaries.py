"""Keep the modular-monolith ownership rules executable during migration."""

import ast

from .boundary_support import (
    APP_ROOT,
    LEGACY_ATTACHMENTS_IMPORTS,
    LEGACY_ATTACHMENTS_SHIMS,
    LEGACY_BILLING_SHIMS,
    LEGACY_CHEMISTRY_SHIMS,
    LEGACY_HOME_SHIMS,
    LEGACY_IMAGES_IMPORTS,
    LEGACY_IMAGES_SHIMS,
    LEGACY_INTEGRATIONS_IMPORTS,
    LEGACY_INTEGRATIONS_SHIMS,
    LEGACY_MATH_SHIMS,
    LEGACY_MEMORY_IMPORTS,
    LEGACY_MEMORY_SHIMS,
    LEGACY_NOTIFICATION_SHIMS,
    LEGACY_PHYSICS_SHIMS,
    LEGACY_SEARCH_SHIMS,
    LEGACY_SPEECH_IMPORTS,
    LEGACY_SPEECH_SHIMS,
    LEGACY_SUGGESTIONS_SHIMS,
    LEGACY_TODOS_IMPORTS,
    LEGACY_TODOS_SHIMS,
    LEGACY_WEB_SEARCH_SHIMS,
    MOBILE_ROOT,
    _imports,
    _production_python,
)


def test_todos_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "todos"
    expected = {
        "actions.py",
        "api.py",
        "classification.py",
        "crud.py",
        "email_repository.py",
        "extract.py",
        "jobs.py",
        "models.py",
        "prompt_context.py",
        "prompt_hint.py",
        "recurrence.py",
        "reminder_fences.py",
        "repository.py",
        "schedule_repository.py",
        "schemas.py",
        "sync.py",
    }
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert {
        "test_api.py",
        "test_email_repository.py",
        "test_recurrence.py",
        "test_repository.py",
        "test_schedule_repository.py",
        "test_schemas.py",
        "test_service.py",
        "test_unique_repository.py",
    } <= {path.name for path in (APP_ROOT / "tests" / "modules" / "todos").glob("*.py")}

    for shim in LEGACY_TODOS_SHIMS:
        tree = ast.parse(shim.read_text(), filename=str(shim))
        owned_definitions = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert not owned_definitions, f"Compatibility shim contains behavior: {shim}"


def test_production_code_does_not_use_legacy_todos_imports() -> None:
    violations: list[str] = []
    for path in _production_python():
        if path in LEGACY_TODOS_SHIMS:
            continue
        for imported in _imports(path):
            if imported.startswith(LEGACY_TODOS_IMPORTS):
                violations.append(f"{path.relative_to(APP_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_infrastructure_does_not_depend_on_product_modules() -> None:
    violations: list[str] = []
    for layer in ("core", "gateways", "repositories"):
        for path in (APP_ROOT / layer).rglob("*.py"):
            if (
                path in LEGACY_TODOS_SHIMS
                or path in LEGACY_MEMORY_SHIMS
                or path in LEGACY_INTEGRATIONS_SHIMS
                or path in LEGACY_ATTACHMENTS_SHIMS
                or path in LEGACY_IMAGES_SHIMS
                or path in LEGACY_SPEECH_SHIMS
                or path in LEGACY_CHEMISTRY_SHIMS
                or path in LEGACY_PHYSICS_SHIMS
                or path in LEGACY_MATH_SHIMS
                or path in LEGACY_WEB_SEARCH_SHIMS
                or path in LEGACY_NOTIFICATION_SHIMS
                or path in LEGACY_HOME_SHIMS
                or path in LEGACY_BILLING_SHIMS
                or path in LEGACY_SEARCH_SHIMS
                or path in LEGACY_SUGGESTIONS_SHIMS
            ):
                continue
            for imported in _imports(path):
                if imported == "app.modules" or imported.startswith("app.modules."):
                    violations.append(f"{path.relative_to(APP_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_the_law_engine_does_not_depend_on_a_subject() -> None:
    """Physics and chemistry share ``services/law_binding``; it may import neither."""
    violations = [
        f"{path.relative_to(APP_ROOT)} imports {imported}"
        for path in (APP_ROOT / "services" / "law_binding").rglob("*.py")
        for imported in _imports(path)
        if imported == "app.modules" or imported.startswith("app.modules.")
    ]
    assert not violations, "\n".join(violations)


def test_mobile_todos_has_one_feature_home_and_thin_route() -> None:
    feature_root = MOBILE_ROOT / "features" / "todos"
    assert (feature_root / "api.ts").is_file()
    for folder in ("components", "context", "hooks", "model", "screens"):
        assert (feature_root / folder).is_dir()

    route = MOBILE_ROOT / "app" / "todos.tsx"
    lines = [line for line in route.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    assert "features/todos/screens/TodosScreen" in lines[0]

    assert not (MOBILE_ROOT / "components" / "todos").exists()
    assert not (MOBILE_ROOT / "contexts" / "TodosContext.tsx").exists()
    assert not (MOBILE_ROOT / "lib" / "todos").exists()
    assert not (MOBILE_ROOT / "lib" / "api" / "todos.ts").exists()
    for name in (
        "useReminderBadgeCount.ts",
        "useTodoReminderState.ts",
        "useTodosActions.ts",
        "useTodosDerivedState.ts",
        "useTodosList.ts",
    ):
        assert not (MOBILE_ROOT / "hooks" / name).exists()

    feature_import_violations = [
        str(path.relative_to(MOBILE_ROOT))
        for path in feature_root.rglob("*.ts*")
        if "__tests__" not in path.parts and "@/app/" in path.read_text()
    ]
    assert not feature_import_violations


def test_memory_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "memory"
    expected = {"api.py", "models.py", "ops.py", "repository.py", "schemas.py"}
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (APP_ROOT / "tests" / "modules" / "memory" / "test_api.py").is_file()

    for shim in LEGACY_MEMORY_SHIMS:
        tree = ast.parse(shim.read_text(), filename=str(shim))
        owned_definitions = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert not owned_definitions, f"Compatibility shim contains behavior: {shim}"

    router_shim = APP_ROOT / "routers" / "memories.py"
    router_tree = ast.parse(router_shim.read_text(), filename=str(router_shim))
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "app.modules.memory.api"
        and any(alias.name == "router" for alias in node.names)
        for node in router_tree.body
    ), "legacy memories router must re-export app.modules.memory.api.router"


def test_production_code_does_not_use_legacy_memory_imports() -> None:
    violations: list[str] = []
    for path in _production_python():
        if path in LEGACY_MEMORY_SHIMS:
            continue
        for imported in _imports(path):
            if imported.startswith(LEGACY_MEMORY_IMPORTS):
                violations.append(f"{path.relative_to(APP_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_mobile_memory_has_one_feature_home_and_thin_routes() -> None:
    feature_root = MOBILE_ROOT / "features" / "memory"
    assert (feature_root / "api.ts").is_file()
    assert (feature_root / "types.ts").is_file()
    for folder in ("components", "hooks", "model", "screens"):
        assert (feature_root / folder).is_dir()

    route_targets = {
        MOBILE_ROOT / "app" / "memory" / "index.tsx": "MemoryScreen",
        MOBILE_ROOT / "app" / "memory" / "[key].tsx": "MemoryDocumentScreen",
        MOBILE_ROOT / "app" / "settings" / "memory-settings.tsx": "MemorySettingsScreen",
    }
    for route, screen in route_targets.items():
        lines = [line for line in route.read_text().splitlines() if line.strip()]
        assert len(lines) == 1
        assert f"features/memory/screens/{screen}" in lines[0]
    # One route home: the nested stack replaced the single memory.tsx route.
    assert not (MOBILE_ROOT / "app" / "memory.tsx").exists()

    assert not (MOBILE_ROOT / "components" / "memory").exists()
    assert not (MOBILE_ROOT / "lib" / "memoryFacts.ts").exists()
    assert not (MOBILE_ROOT / "lib" / "cache" / "memoryListCache.ts").exists()
    assert not (MOBILE_ROOT / "lib" / "api" / "memories.ts").exists()
    for name in ("useMemoryActions.ts", "useMemoryToggle.ts"):
        assert not (MOBILE_ROOT / "hooks" / name).exists()

    feature_import_violations = [
        str(path.relative_to(MOBILE_ROOT))
        for path in feature_root.rglob("*.ts*")
        if "__tests__" not in path.parts and "@/app/" in path.read_text()
    ]
    assert not feature_import_violations


def test_integrations_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "integrations"
    expected = {
        "api.py",
        "calendar_repository.py",
        "gmail_api.py",
        "gmail_repository.py",
        "jobs.py",
        "models.py",
        "scheduler.py",
        "schemas.py",
        "suggestions_repository.py",
        "tool.py",
    }
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (APP_ROOT / "tests" / "modules" / "integrations" / "test_gmail.py").is_file()

    for shim in LEGACY_INTEGRATIONS_SHIMS:
        tree = ast.parse(shim.read_text(), filename=str(shim))
        owned_definitions = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert not owned_definitions, f"Compatibility shim contains behavior: {shim}"

    for filename, module in (
        ("integrations.py", "app.modules.integrations.api"),
        ("gmail_integrations.py", "app.modules.integrations.gmail_api"),
    ):
        shim = APP_ROOT / "routers" / filename
        shim_tree = ast.parse(shim.read_text(), filename=str(shim))
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == module
            and any(alias.name == "router" for alias in node.names)
            for node in shim_tree.body
        ), f"legacy {filename} must re-export router"


def test_production_code_does_not_use_legacy_integrations_imports() -> None:
    violations: list[str] = []
    for path in _production_python():
        if path in LEGACY_INTEGRATIONS_SHIMS:
            continue
        for imported in _imports(path):
            if imported.startswith(LEGACY_INTEGRATIONS_IMPORTS):
                violations.append(f"{path.relative_to(APP_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_mobile_integrations_has_one_feature_home_and_thin_routes() -> None:
    feature_root = MOBILE_ROOT / "features" / "integrations"
    assert (feature_root / "api.ts").is_file()
    assert (feature_root / "types.ts").is_file()
    for folder in ("components", "context", "hooks", "model", "screens"):
        assert (feature_root / folder).is_dir()

    route = MOBILE_ROOT / "app" / "settings" / "integrations.tsx"
    lines = [line for line in route.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    assert "features/integrations/screens/IntegrationsScreen" in lines[0]

    for gone in (
        MOBILE_ROOT / "lib" / "api" / "integrations.ts",
        MOBILE_ROOT / "lib" / "google-calendar.ts",
        MOBILE_ROOT / "lib" / "google-gmail.ts",
        MOBILE_ROOT / "lib" / "google-integration-auth.ts",
        MOBILE_ROOT / "lib" / "calendarProposal.ts",
        MOBILE_ROOT / "lib" / "gmailAutoSync.ts",
        MOBILE_ROOT / "lib" / "cache" / "integrationStatusCache.ts",
        MOBILE_ROOT / "hooks" / "useSettingsIntegrations.ts",
        MOBILE_ROOT / "hooks" / "useCalendarProposal.ts",
        MOBILE_ROOT / "components" / "CalendarProposalCard.tsx",
        MOBILE_ROOT / "components" / "rich" / "EmailCard.tsx",
        MOBILE_ROOT / "contexts" / "emailDraftPersist.tsx",
    ):
        assert not gone.exists(), gone

    feature_import_violations = [
        str(path.relative_to(MOBILE_ROOT))
        for path in feature_root.rglob("*.ts*")
        if "__tests__" not in path.parts and "@/app/" in path.read_text()
    ]
    assert not feature_import_violations


def test_attachments_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "attachments"
    expected = {
        "api.py",
        "chunks_repository.py",
        "jobs.py",
        "models.py",
        "reaper.py",
        "repository.py",
        "schemas.py",
    }
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (APP_ROOT / "tests" / "modules" / "attachments" / "test_api.py").is_file()

    for shim in LEGACY_ATTACHMENTS_SHIMS:
        tree = ast.parse(shim.read_text(), filename=str(shim))
        owned_definitions = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert not owned_definitions, f"Compatibility shim contains behavior: {shim}"

    shim = APP_ROOT / "routers" / "attachments.py"
    shim_tree = ast.parse(shim.read_text(), filename=str(shim))
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "app.modules.attachments.api"
        and any(alias.name == "router" for alias in node.names)
        for node in shim_tree.body
    ), "legacy attachments router must re-export router"


def test_production_code_does_not_use_legacy_attachments_imports() -> None:
    violations: list[str] = []
    for path in _production_python():
        if path in LEGACY_ATTACHMENTS_SHIMS:
            continue
        for imported in _imports(path):
            if imported.startswith(LEGACY_ATTACHMENTS_IMPORTS):
                violations.append(f"{path.relative_to(APP_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_mobile_attachments_has_one_feature_home_and_thin_routes() -> None:
    feature_root = MOBILE_ROOT / "features" / "attachments"
    assert (feature_root / "api.ts").is_file()
    assert (feature_root / "types.ts").is_file()
    for folder in ("components", "hooks", "model", "screens"):
        assert (feature_root / folder).is_dir()

    route = MOBILE_ROOT / "app" / "gallery.tsx"
    lines = [line for line in route.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    assert "features/attachments/screens/GalleryScreen" in lines[0]

    for gone in (
        MOBILE_ROOT / "lib" / "api" / "attachments.ts",
        MOBILE_ROOT / "lib" / "attachments.ts",
        MOBILE_ROOT / "lib" / "gallery.ts",
        MOBILE_ROOT / "lib" / "galleryLayout.ts",
        MOBILE_ROOT / "lib" / "cache" / "galleryListCache.ts",
        MOBILE_ROOT / "hooks" / "useGalleryData.ts",
        MOBILE_ROOT / "hooks" / "useGalleryLibrary.ts",
        MOBILE_ROOT / "hooks" / "useAttachmentIndexed.ts",
        MOBILE_ROOT / "components" / "GalleryThumbnail.tsx",
        MOBILE_ROOT / "components" / "AttachmentSourceSheet.tsx",
        MOBILE_ROOT / "components" / "gallery",
    ):
        assert not gone.exists(), gone

    feature_import_violations = [
        str(path.relative_to(MOBILE_ROOT))
        for path in feature_root.rglob("*.ts*")
        if "__tests__" not in path.parts and "@/app/" in path.read_text()
    ]
    assert not feature_import_violations


def test_images_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "images"
    expected = {
        "api.py",
        "gen_intent.py",
        "gen_tool.py",
        "generation.py",
        "lookup_intent.py",
        "schemas.py",
        "search.py",
        "search_tool.py",
    }
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (APP_ROOT / "tests" / "modules" / "images" / "test_api.py").is_file()

    for shim in LEGACY_IMAGES_SHIMS:
        tree = ast.parse(shim.read_text(), filename=str(shim))
        owned_definitions = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert not owned_definitions, f"Compatibility shim contains behavior: {shim}"

    shim = APP_ROOT / "routers" / "images.py"
    shim_tree = ast.parse(shim.read_text(), filename=str(shim))
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "app.modules.images.api"
        and any(alias.name == "router" for alias in node.names)
        for node in shim_tree.body
    ), "legacy images router must re-export router"

    # schemas.py imports MessageOut from chats, which loads this package first.
    # Re-exporting the image models here imports the module while it is still initializing.
    schema_barrel = APP_ROOT / "models" / "schemas" / "__init__.py"
    assert not any(
        imported == "app.modules.images" or imported.startswith("app.modules.images.")
        for imported in _imports(schema_barrel)
    )


def test_production_code_does_not_use_legacy_images_imports() -> None:
    violations: list[str] = []
    for path in _production_python():
        if path in LEGACY_IMAGES_SHIMS:
            continue
        for imported in _imports(path):
            if imported.startswith(LEGACY_IMAGES_IMPORTS):
                violations.append(f"{path.relative_to(APP_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_mobile_images_has_one_feature_home() -> None:
    feature_root = MOBILE_ROOT / "features" / "images"
    assert (feature_root / "api.ts").is_file()
    assert (feature_root / "types.ts").is_file()
    for folder in ("components", "hooks", "model"):
        assert (feature_root / folder).is_dir()

    for gone in (
        MOBILE_ROOT / "lib" / "api" / "images.ts",
        MOBILE_ROOT / "lib" / "images" / "imageGenIntent.ts",
        MOBILE_ROOT / "lib" / "images" / "imageLookupIntent.ts",
        MOBILE_ROOT / "lib" / "images" / "imageGenTurn.ts",
        MOBILE_ROOT / "hooks" / "useImageGeneration.ts",
        MOBILE_ROOT / "components" / "ImageGenPlaceholder.tsx",
        MOBILE_ROOT / "components" / "ImageGenPromptSheet.tsx",
    ):
        assert not gone.exists(), gone
    assert (MOBILE_ROOT / "lib" / "images" / "imageUriPolicy.ts").is_file()

    feature_import_violations = [
        str(path.relative_to(MOBILE_ROOT))
        for path in feature_root.rglob("*.ts*")
        if "__tests__" not in path.parts and "@/app/" in path.read_text()
    ]
    assert not feature_import_violations


def test_speech_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "speech"
    expected = {
        "api.py",
        "live_talk.py",
        "live_talk_tools.py",
        "realtime.py",
        "schemas.py",
        "service.py",
    }
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (APP_ROOT / "tests" / "modules" / "speech" / "test_service.py").is_file()

    for shim in LEGACY_SPEECH_SHIMS:
        tree = ast.parse(shim.read_text(), filename=str(shim))
        owned_definitions = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert not owned_definitions, f"Compatibility shim contains behavior: {shim}"

    for shim_name, module_name in (("speech.py", "api"), ("speech_realtime.py", "realtime")):
        shim = APP_ROOT / "routers" / shim_name
        shim_tree = ast.parse(shim.read_text(), filename=str(shim))
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == f"app.modules.speech.{module_name}"
            and any(alias.name == "router" for alias in node.names)
            for node in shim_tree.body
        ), f"legacy {shim_name} must re-export router"

    schema_barrel = APP_ROOT / "models" / "schemas" / "__init__.py"
    assert not any(
        imported == "app.modules.speech" or imported.startswith("app.modules.speech.")
        for imported in _imports(schema_barrel)
    )


def test_production_code_does_not_use_legacy_speech_imports() -> None:
    violations: list[str] = []
    for path in _production_python():
        if path in LEGACY_SPEECH_SHIMS:
            continue
        for imported in _imports(path):
            if imported.startswith(LEGACY_SPEECH_IMPORTS):
                violations.append(f"{path.relative_to(APP_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_mobile_speech_has_one_feature_home() -> None:
    feature_root = MOBILE_ROOT / "features" / "speech"
    assert (feature_root / "api.ts").is_file()
    assert (feature_root / "types.ts").is_file()
    for folder in ("components", "hooks", "model"):
        assert (feature_root / folder).is_dir()

    for gone in (
        MOBILE_ROOT / "lib" / "api" / "speech.ts",
        MOBILE_ROOT / "hooks" / "useLiveTalk.ts",
        MOBILE_ROOT / "hooks" / "useVoiceInput.ts",
        MOBILE_ROOT / "lib" / "speech" / "pronunciation.ts",
        MOBILE_ROOT / "lib" / "speech" / "realtimeVoice.ts",
        MOBILE_ROOT / "components" / "chat" / "LiveTalkOverlay.tsx",
        MOBILE_ROOT / "components" / "chat" / "VoiceMicButton.tsx",
    ):
        assert not gone.exists(), gone
    assert (MOBILE_ROOT / "lib" / "speech" / "voiceAudio.ts").is_file()

    feature_import_violations = [
        str(path.relative_to(MOBILE_ROOT))
        for path in feature_root.rglob("*.ts*")
        if "__tests__" not in path.parts and "@/app/" in path.read_text()
    ]
    assert not feature_import_violations
