"""Shared paths, legacy catalogs, and checks for module-boundary tests."""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_ROOT.parents[2]
MOBILE_ROOT = REPO_ROOT / "apps" / "mobile"

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
LEGACY_PHYSICS_SHIMS = {
    APP_ROOT / "services" / "physics" / "__init__.py",
}
LEGACY_MATH_SHIMS = {
    APP_ROOT / "services" / "math" / "__init__.py",
    APP_ROOT / "services" / "mcp" / "sympy_adapter.py",
}
LEGACY_WEB_SEARCH_SHIMS = {
    APP_ROOT / "services" / "web_search" / "__init__.py",
    APP_ROOT / "services" / "mcp" / "web_search_adapter.py",
}
LEGACY_NOTIFICATION_SHIMS = {
    APP_ROOT / "services" / "notifications" / "__init__.py",
}
LEGACY_HOME_SHIMS = {
    APP_ROOT / "routers" / "home.py",
    APP_ROOT / "services" / "home" / "__init__.py",
}
LEGACY_HOME_IMPORTS = (
    "app.routers.home",
    "app.services.home",
)
LEGACY_BILLING_SHIMS = {
    APP_ROOT / "services" / "plan.py",
    APP_ROOT / "services" / "subscription.py",
    APP_ROOT / "services" / "revenuecat_webhook.py",
    APP_ROOT / "routers" / "webhooks.py",
}
LEGACY_SEARCH_SHIMS = {
    APP_ROOT / "repositories" / "search.py",
    APP_ROOT / "routers" / "search.py",
    APP_ROOT / "services" / "search.py",
}
LEGACY_SEARCH_IMPORTS = (
    "app.repositories.search",
    "app.routers.search",
    "app.services.search",
)
LEGACY_SUGGESTIONS_SHIMS = {
    APP_ROOT / "background" / "suggestion_generation.py",
    APP_ROOT / "models" / "orm" / "suggestions.py",
    APP_ROOT / "repositories" / "suggestions.py",
    APP_ROOT / "routers" / "suggestions.py",
    APP_ROOT / "services" / "suggestion_generation.py",
}
LEGACY_SUGGESTIONS_IMPORTS = (
    "app.background.suggestion_generation",
    "app.models.orm.suggestions",
    "app.repositories.suggestions",
    "app.routers.suggestions",
    "app.services.suggestion_generation",
)
LEGACY_CHAT_SHIMS = {
    APP_ROOT / "routers" / "chats.py",
    APP_ROOT / "services" / "chats.py",
}
LEGACY_CHAT_IMPORTS = (
    "app.routers.chats",
    "app.services.chats",
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


def _shim_has_no_behavior(shim: Path) -> None:
    tree = ast.parse(shim.read_text(), filename=str(shim))
    owned_definitions = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    assert not owned_definitions, f"Compatibility shim contains behavior: {shim}"


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
            elif target.id in {"__all__", "_MODULE_EXPORTS"} and isinstance(
                node.value, ast.List | ast.Tuple
            ):
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
