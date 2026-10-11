"""Shared paths, legacy catalogs, and checks for module-boundary tests."""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_ROOT.parents[2]
MOBILE_ROOT = REPO_ROOT / "apps" / "mobile"

# Compatibility paths left behind by the module migrations. Each one was deleted
# once nothing imported it; ``test_legacy_paths_removed`` keeps them gone.
RETIRED_LEGACY_MODULES: tuple[str, ...] = (
    "app.background.attachment_indexing",
    "app.background.attachment_orphan_reaper",
    "app.background.compaction",
    "app.background.gmail_periodic_sync",
    "app.background.gmail_sync",
    "app.background.memory_consolidation",
    "app.background.memory_extraction",
    "app.background.suggestion_generation",
    "app.background.todo_sync",
    "app.models.memory_ops",
    "app.models.orm.memory",
    "app.models.orm.schedule",
    "app.models.orm.suggestions",
    "app.models.schemas.attachments",
    "app.models.schemas.memory",
    "app.models.schemas.schedule",
    "app.modules.chemistry.legacy_alias",
    "app.modules.home.legacy_alias",
    "app.modules.math.legacy_alias",
    "app.modules.math.sympy_executor",
    "app.modules.notifications.legacy_alias",
    "app.modules.physics.legacy_alias",
    "app.modules.web_search.legacy_alias",
    "app.repositories.attachment_chunks",
    "app.repositories.attachments",
    "app.repositories.calendar_connections",
    "app.repositories.gmail_connections",
    "app.repositories.memories",
    "app.repositories.memory_writes",
    "app.repositories.search",
    "app.repositories.suggested_reminders",
    "app.repositories.suggestions",
    "app.repositories.todo_email",
    "app.repositories.todo_schedules",
    "app.repositories.todos",
    "app.routers.attachments",
    "app.routers.chats",
    "app.routers.gmail_integrations",
    "app.routers.home",
    "app.routers.images",
    "app.routers.integrations",
    "app.routers.memories",
    "app.routers.search",
    "app.routers.speech",
    "app.routers.speech_realtime",
    "app.routers.suggestions",
    "app.routers.todos",
    "app.routers.webhooks",
    "app.services.attachments",
    "app.services.calendar",
    "app.services.calendar_nudges",
    "app.services.chats",
    "app.services.chemistry",
    "app.services.email.context",
    "app.services.email.fence",
    "app.services.email.sender_templates",
    "app.services.email.triage",
    "app.services.google_integrations",
    "app.services.home",
    "app.services.images",
    "app.services.live_talk",
    "app.services.live_talk_tools",
    "app.services.math",
    "app.services.mcp.calendar_adapter",
    "app.services.mcp.image_gen_adapter",
    "app.services.mcp.image_search_adapter",
    "app.services.mcp.sympy_adapter",
    "app.services.mcp.web_search_adapter",
    "app.services.memory",
    "app.services.notifications",
    "app.services.physics",
    "app.services.plan",
    "app.services.revenuecat_webhook",
    "app.services.search",
    "app.services.speech",
    "app.services.sympy_executor",
    "app.services.subscription",
    "app.services.suggestion_generation",
    "app.services.todos",
    "app.services.web_search",
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
