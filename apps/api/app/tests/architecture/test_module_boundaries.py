"""Keep the modular-monolith ownership rules executable during migration."""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_ROOT.parents[2]
MOBILE_ROOT = REPO_ROOT / "apps" / "mobile"

LEGACY_JOB_SEARCH_SHIMS = {
    APP_ROOT / "background" / "job_search_jobs.py",
    APP_ROOT / "background" / "job_search_scheduler.py",
    APP_ROOT / "models" / "orm" / "job_search.py",
    APP_ROOT / "models" / "schemas" / "job_search.py",
    APP_ROOT / "routers" / "job_search.py",
    APP_ROOT / "services" / "job_search" / "__init__.py",
    APP_ROOT / "services" / "job_search" / "chat_intent.py",
    APP_ROOT / "services" / "job_search" / "notifications.py",
    APP_ROOT / "services" / "job_search" / "runner.py",
    APP_ROOT / "services" / "mcp" / "job_search_adapter.py",
}
LEGACY_JOB_SEARCH_IMPORTS = (
    "app.background.job_search_jobs",
    "app.background.job_search_scheduler",
    "app.models.orm.job_search",
    "app.models.schemas.job_search",
    "app.routers.job_search",
    "app.services.job_search",
    "app.services.mcp.job_search_adapter",
)
LEGACY_TODOS_SHIMS = {
    APP_ROOT / "background" / "todo_sync.py",
    APP_ROOT / "models" / "orm" / "schedule.py",
    APP_ROOT / "models" / "schemas" / "schedule.py",
    APP_ROOT / "repositories" / "todo_email.py",
    APP_ROOT / "repositories" / "todo_schedules.py",
    APP_ROOT / "repositories" / "todos.py",
    APP_ROOT / "routers" / "todos.py",
    *(
        APP_ROOT / "services" / "todos" / name
        for name in (
            "__init__.py",
            "actions.py",
            "classification.py",
            "crud.py",
            "extract.py",
            "prompt_context.py",
            "prompt_hint.py",
            "recurrence.py",
            "reminder_fences.py",
            "sync.py",
        )
    ),
}
LEGACY_TODOS_IMPORTS = (
    "app.background.todo_sync",
    "app.models.orm.schedule",
    "app.models.schemas.schedule",
    "app.repositories.todo_email",
    "app.repositories.todo_schedules",
    "app.repositories.todos",
    "app.routers.todos",
    "app.services.todos",
)
LEGACY_LEARNING_SHIMS = {
    APP_ROOT / "background" / "learning_sync.py",
    APP_ROOT / "core" / "learning_policy.py",
    APP_ROOT / "models" / "orm" / "learning.py",
    APP_ROOT / "models" / "orm" / "learning_practice.py",
    APP_ROOT / "models" / "schemas" / "learning.py",
    APP_ROOT / "repositories" / "learning.py",
    APP_ROOT / "repositories" / "learning_activity.py",
    APP_ROOT / "repositories" / "learning_catalog.py",
    APP_ROOT / "repositories" / "learning_export.py",
    APP_ROOT / "repositories" / "learning_items.py",
    APP_ROOT / "repositories" / "learning_practice.py",
    APP_ROOT / "routers" / "learning.py",
    APP_ROOT / "services" / "chat" / "learning_fences.py",
    APP_ROOT / "services" / "home" / "learning_starters.py",
    *(
        APP_ROOT / "services" / "learning" / name
        for name in (
            "__init__.py",
            "actions.py",
            "catalog_items.py",
            "catalog_sync.py",
            "common.py",
            "crud.py",
            "daily.py",
            "extract.py",
            "insights.py",
            "items.py",
            "nudges.py",
            "path.py",
            "path_seed.py",
            "practice.py",
            "practice_context.py",
            "practice_history.py",
            "prompt_context.py",
            "prompts.py",
            "quiz_grading.py",
            "spaced_repetition.py",
            "stats.py",
            "sync.py",
        )
    ),
}
LEGACY_LEARNING_IMPORTS = (
    "app.background.learning_sync",
    "app.core.learning_policy",
    "app.models.orm.learning",
    "app.models.schemas.learning",
    "app.repositories.learning",
    "app.routers.learning",
    "app.services.chat.learning_fences",
    "app.services.home.learning_starters",
    "app.services.learning",
)
LEGACY_MEMORY_SHIMS = {
    APP_ROOT / "models" / "memory_ops.py",
    APP_ROOT / "models" / "orm" / "memory.py",
    APP_ROOT / "models" / "schemas" / "memory.py",
    APP_ROOT / "repositories" / "memories.py",
    APP_ROOT / "repositories" / "memory_writes.py",
    APP_ROOT / "routers" / "memories.py",
    *(
        APP_ROOT / "services" / "memory" / name
        for name in (
            "__init__.py",
            "apply.py",
            "cache.py",
            "consolidation.py",
            "consolidation_workflow.py",
            "crud.py",
            "enqueue_policy.py",
            "extract_backlog.py",
            "extraction_workflow.py",
            "facts.py",
            "llm.py",
            "locks.py",
            "retrieval.py",
            "selection.py",
            "text.py",
        )
    ),
}
LEGACY_MEMORY_IMPORTS = (
    "app.models.memory_ops",
    "app.models.orm.memory",
    "app.models.schemas.memory",
    "app.repositories.memories",
    "app.repositories.memory_writes",
    "app.routers.memories",
    "app.services.memory",
)
LEGACY_INTEGRATIONS_SHIMS = {
    APP_ROOT / "background" / "gmail_periodic_sync.py",
    APP_ROOT / "background" / "gmail_sync.py",
    APP_ROOT / "repositories" / "calendar_connections.py",
    APP_ROOT / "repositories" / "gmail_connections.py",
    APP_ROOT / "repositories" / "suggested_reminders.py",
    APP_ROOT / "routers" / "gmail_integrations.py",
    APP_ROOT / "routers" / "integrations.py",
    APP_ROOT / "services" / "calendar.py",
    APP_ROOT / "services" / "calendar_nudges.py",
    APP_ROOT / "services" / "google_integrations.py",
    APP_ROOT / "services" / "mcp" / "calendar_adapter.py",
    *(
        APP_ROOT / "services" / "email" / name
        for name in (
            "__init__.py",
            "context.py",
            "fence.py",
            "sender_templates.py",
            "triage.py",
        )
    ),
}
LEGACY_INTEGRATIONS_IMPORTS = (
    "app.background.gmail_periodic_sync",
    "app.background.gmail_sync",
    "app.repositories.calendar_connections",
    "app.repositories.gmail_connections",
    "app.repositories.suggested_reminders",
    "app.routers.gmail_integrations",
    "app.routers.integrations",
    "app.services.calendar",
    "app.services.calendar_nudges",
    "app.services.email",
    "app.services.google_integrations",
    "app.services.mcp.calendar_adapter",
)
LEGACY_ATTACHMENTS_SHIMS = {
    APP_ROOT / "background" / "attachment_indexing.py",
    APP_ROOT / "background" / "attachment_orphan_reaper.py",
    APP_ROOT / "models" / "schemas" / "attachments.py",
    APP_ROOT / "repositories" / "attachment_chunks.py",
    APP_ROOT / "repositories" / "attachments.py",
    APP_ROOT / "routers" / "attachments.py",
    *(
        APP_ROOT / "services" / "attachments" / name
        for name in (
            "__init__.py",
            "content.py",
            "lifecycle.py",
            "ocr.py",
            "quota.py",
            "rag.py",
            "reuse.py",
            "upload.py",
            "workflow.py",
        )
    ),
}
LEGACY_ATTACHMENTS_IMPORTS = (
    "app.background.attachment_indexing",
    "app.background.attachment_orphan_reaper",
    "app.models.schemas.attachments",
    "app.repositories.attachment_chunks",
    "app.repositories.attachments",
    "app.routers.attachments",
    "app.services.attachments",
)
LEGACY_IMAGES_SHIMS = {
    APP_ROOT / "routers" / "images.py",
    APP_ROOT / "services" / "mcp" / "image_gen_adapter.py",
    APP_ROOT / "services" / "mcp" / "image_search_adapter.py",
    *(
        APP_ROOT / "services" / "images" / name
        for name in (
            "__init__.py",
            "gen_intent.py",
            "generation.py",
            "lookup_intent.py",
            "search.py",
        )
    ),
}
LEGACY_IMAGES_IMPORTS = (
    "app.routers.images",
    "app.services.images",
    "app.services.mcp.image_gen_adapter",
    "app.services.mcp.image_search_adapter",
)
LEGACY_SPEECH_SHIMS = {
    APP_ROOT / "routers" / "speech.py",
    APP_ROOT / "routers" / "speech_realtime.py",
    APP_ROOT / "services" / "speech.py",
    APP_ROOT / "services" / "live_talk.py",
    APP_ROOT / "services" / "live_talk_tools.py",
}
LEGACY_SPEECH_IMPORTS = (
    "app.routers.speech",
    "app.routers.speech_realtime",
    "app.services.speech",
    "app.services.live_talk",
    "app.services.live_talk_tools",
)
LEGACY_CHEMISTRY_SHIMS = {
    APP_ROOT / "services" / "chemistry" / "__init__.py",
}


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _production_python() -> list[Path]:
    return [
        path
        for path in APP_ROOT.rglob("*.py")
        if "tests" not in path.parts and "__pycache__" not in path.parts
    ]


def test_job_search_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "job_search"
    expected = {
        "api.py",
        "chat_intent.py",
        "jobs.py",
        "models.py",
        "notifications.py",
        "runner.py",
        "scheduler.py",
        "schemas.py",
        "service.py",
        "tool.py",
    }
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert {
        "test_api.py",
        "test_jobs.py",
        "test_runner.py",
        "test_service.py",
        "test_tool.py",
    } <= {path.name for path in (APP_ROOT / "tests" / "modules" / "job_search").glob("*.py")}

    for shim in LEGACY_JOB_SEARCH_SHIMS:
        tree = ast.parse(shim.read_text(), filename=str(shim))
        owned_definitions = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert not owned_definitions, f"Compatibility shim contains behavior: {shim}"


def test_production_code_does_not_use_legacy_job_search_imports() -> None:
    violations: list[str] = []
    for path in _production_python():
        if path in LEGACY_JOB_SEARCH_SHIMS:
            continue
        for imported in _imports(path):
            if imported.startswith(LEGACY_JOB_SEARCH_IMPORTS):
                violations.append(f"{path.relative_to(APP_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


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
                or path in LEGACY_LEARNING_SHIMS
                or path in LEGACY_MEMORY_SHIMS
                or path in LEGACY_INTEGRATIONS_SHIMS
                or path in LEGACY_ATTACHMENTS_SHIMS
                or path in LEGACY_IMAGES_SHIMS
                or path in LEGACY_SPEECH_SHIMS
                or path in LEGACY_CHEMISTRY_SHIMS
            ):
                continue
            for imported in _imports(path):
                if imported == "app.modules" or imported.startswith("app.modules."):
                    violations.append(f"{path.relative_to(APP_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_mobile_job_search_has_one_feature_home_and_thin_routes() -> None:
    feature_root = MOBILE_ROOT / "features" / "job-search"
    assert (feature_root / "api.ts").is_file()
    for folder in ("components", "hooks", "model", "screens"):
        assert (feature_root / folder).is_dir()

    route_targets = {
        MOBILE_ROOT / "app" / "my-job" / "index.tsx": "MyJobScreen",
        MOBILE_ROOT / "app" / "my-job" / "setup.tsx": "MyJobSetupScreen",
        MOBILE_ROOT / "app" / "my-job" / "match" / "[id].tsx": "JobMatchDetailScreen",
    }
    for route, screen in route_targets.items():
        lines = [line for line in route.read_text().splitlines() if line.strip()]
        assert len(lines) == 1
        assert f"features/job-search/screens/{screen}" in lines[0]

    assert not (MOBILE_ROOT / "components" / "jobSearch").exists()
    assert not (MOBILE_ROOT / "lib" / "jobSearch").exists()
    assert not (MOBILE_ROOT / "lib" / "api" / "jobSearch.ts").exists()
    assert not (MOBILE_ROOT / "hooks" / "useJobSearch.ts").exists()
    assert not (MOBILE_ROOT / "hooks" / "useJobMatchDetail.ts").exists()

    feature_import_violations = [
        str(path.relative_to(MOBILE_ROOT))
        for path in feature_root.rglob("*.ts*")
        if "__tests__" not in path.parts and "@/app/" in path.read_text()
    ]
    assert not feature_import_violations


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


def test_learning_runtime_code_has_one_owner() -> None:
    module_root = APP_ROOT / "modules" / "learning"
    expected = {
        "access.py",
        "api.py",
        "errors.py",
        "jobs.py",
        "models.py",
        "policy.py",
        "repository.py",
        "schemas.py",
    }
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (APP_ROOT / "tests" / "modules" / "learning" / "test_api.py").is_file()

    for shim in LEGACY_LEARNING_SHIMS:
        tree = ast.parse(shim.read_text(), filename=str(shim))
        owned_definitions = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert not owned_definitions, f"Compatibility shim contains behavior: {shim}"


def test_production_code_does_not_use_legacy_learning_imports() -> None:
    violations: list[str] = []
    for path in _production_python():
        if path in LEGACY_LEARNING_SHIMS:
            continue
        for imported in _imports(path):
            if imported.startswith(LEGACY_LEARNING_IMPORTS):
                violations.append(f"{path.relative_to(APP_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


def test_mobile_learning_has_one_feature_home_and_thin_routes() -> None:
    feature_root = MOBILE_ROOT / "features" / "learning"
    assert (feature_root / "api.ts").is_file()
    assert (feature_root / "types.ts").is_file()
    for folder in ("components", "context", "hooks", "model", "screens"):
        assert (feature_root / folder).is_dir()

    route_targets = {
        MOBILE_ROOT / "app" / "projects" / "index.tsx": "LearningListScreen",
        MOBILE_ROOT / "app" / "projects" / "create.tsx": "LearningCreateScreen",
        MOBILE_ROOT / "app" / "projects" / "[id]" / "index.tsx": "LearningDetailRedirect",
        MOBILE_ROOT / "app" / "projects" / "[id]" / "lesson" / "index.tsx": "LessonMapScreen",
        MOBILE_ROOT / "app" / "projects" / "[id]" / "lesson" / "play.tsx": "LessonPlayScreen",
    }
    for route, screen in route_targets.items():
        lines = [line for line in route.read_text().splitlines() if line.strip()]
        assert len(lines) == 1
        assert f"features/learning/screens/{screen}" in lines[0]

    assert not (MOBILE_ROOT / "components" / "projects").exists()
    assert not (MOBILE_ROOT / "contexts" / "ProjectsContext.tsx").exists()
    assert not (MOBILE_ROOT / "lib" / "projects").exists()
    assert not (MOBILE_ROOT / "lib" / "api" / "learning.ts").exists()
    for name in (
        "useLearningDetail.ts",
        "useLessonSession.ts",
        "useProjectActions.ts",
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
        MOBILE_ROOT / "app" / "memory.tsx": "MemoryScreen",
        MOBILE_ROOT / "app" / "settings" / "memory-settings.tsx": "MemorySettingsScreen",
    }
    for route, screen in route_targets.items():
        lines = [line for line in route.read_text().splitlines() if line.strip()]
        assert len(lines) == 1
        assert f"features/memory/screens/{screen}" in lines[0]

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
        "solutions.py",
        "stoichiometry.py",
    }
    assert expected <= {path.name for path in module_root.glob("*.py")}
    assert (module_root / "solvers" / "solver.py").is_file()
    assert (APP_ROOT / "tests" / "modules" / "chemistry" / "test_chemistry_service.py").is_file()

    for shim in LEGACY_CHEMISTRY_SHIMS:
        tree = ast.parse(shim.read_text(), filename=str(shim))
        owned_definitions = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        assert not owned_definitions, f"Compatibility shim contains behavior: {shim}"

    assert not (MOBILE_ROOT / "features" / "chemistry").exists()
    assert (MOBILE_ROOT / "lib" / "chemistry" / "fence.ts").is_file()


def test_production_code_does_not_use_legacy_chemistry_imports() -> None:
    violations: list[str] = []
    for path in _production_python():
        if path in LEGACY_CHEMISTRY_SHIMS:
            continue
        for imported in _imports(path):
            if imported == "app.services.chemistry" or imported.startswith(
                "app.services.chemistry."
            ):
                violations.append(f"{path.relative_to(APP_ROOT)} imports {imported}")
    assert not violations, "\n".join(violations)


_PUBLIC_MODULE_TAILS = frozenset({"api", "schemas", "service", "crud"})


def _package_public_names(module_name: str) -> frozenset[str]:
    """Public tails plus names the package initializer actually exports."""
    names = set(_PUBLIC_MODULE_TAILS)
    init = APP_ROOT / "modules" / module_name / "__init__.py"
    if not init.is_file():
        return frozenset(names)
    tree = ast.parse(init.read_text(), filename=str(init))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "_EXPORTS" and isinstance(node.value, ast.Dict):
                names.update(
                    key.value
                    for key in node.value.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                )
            elif target.id == "__all__" and isinstance(node.value, ast.List | ast.Tuple):
                names.update(
                    item.value
                    for item in node.value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                )
    return frozenset(names)


def _foreign_module_import_violations(tree: ast.AST, *, owner: str, label: str) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        bindings: list[tuple[str, str | None]]
        if isinstance(node, ast.Import):
            bindings = [(alias.name, None) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            bindings = [(node.module, alias.name) for alias in node.names]
        else:
            continue
        for module_name, symbol in bindings:
            if not module_name.startswith("app.modules."):
                continue
            parts = module_name.removeprefix("app.modules.").split(".")
            other = parts[0]
            if other == owner:
                continue
            if len(parts) == 1:
                if symbol is None:
                    continue
                if symbol == "*" or symbol not in _package_public_names(other):
                    violations.append(f"{label} imports {symbol} from {module_name}")
                continue
            if parts[1] not in _PUBLIC_MODULE_TAILS:
                violations.append(f"{label} imports {module_name}")
    return violations


def test_package_import_cannot_pull_a_private_name() -> None:
    leaked = ast.parse("from app.modules.attachments import repository\n")
    violations = _foreign_module_import_violations(leaked, owner="images", label="sample")
    assert violations == ["sample imports repository from app.modules.attachments"]

    public = ast.parse(
        "from app.modules.attachments import service\n"
        "from app.modules.todos import snap_first_due\n"
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
