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
            if path in LEGACY_TODOS_SHIMS:
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
