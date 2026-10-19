"""Shared paths, legacy catalogs, and checks for module-boundary tests."""

from __future__ import annotations

import ast
from collections import deque
from collections.abc import Iterable
from functools import cache
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
    # A one-line re-export of ``services.topic.generate_chat_title``.
    "app.background.topic_generation",
    "app.models.memory_ops",
    # Held only PushToken after the Google integrations were removed: ``orm.push_tokens``.
    "app.models.orm.integrations",
    "app.models.orm.memory",
    "app.models.orm.schedule",
    "app.models.orm.suggestions",
    "app.models.schemas.attachments",
    "app.models.schemas.chemistry",
    # Split into ``classification`` and ``push``; its speech re-exports had no importer.
    "app.models.schemas.integrations",
    "app.models.schemas.math",
    "app.models.schemas.memory",
    "app.models.schemas.physics",
    "app.models.schemas.schedule",
    "app.modules.chat.prompt_constants.physics",
    # The chat stream's seam module: stages take ``turn_deps.ChatTurnDeps`` (ES-23).
    "app.modules.chat.stream",
    "app.modules.chemistry.legacy_alias",
    "app.modules.home.legacy_alias",
    "app.modules.math.legacy_alias",
    # Split by job: ``equations``, ``equation_conditions``, ``root_latex``, ``systems``,
    # ``numeric``, ``expressions``, ``inequalities`` (ES-34).
    "app.modules.math.solve.algebra",
    "app.modules.math.sympy_executor",
    # Split by job: ``request_text``, ``expr_rewrite``, ``function_def``, ``direct_newton`` (ES-34).
    "app.modules.math.tools.helpers",
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
    "app.routers.analytics",
    "app.routers.attachments",
    "app.routers.auth",
    "app.routers.chat_stream",
    "app.routers.chats",
    "app.routers.gmail_integrations",
    "app.routers.home",
    "app.routers.images",
    "app.routers.integrations",
    "app.routers.link_preview",
    "app.routers.memories",
    "app.routers.search",
    "app.routers.speech",
    "app.routers.speech_realtime",
    "app.routers.suggestions",
    "app.routers.todos",
    "app.routers.users",
    "app.routers.webhooks",
    "app.routers.ws",
    "app.services.account_lifecycle",
    "app.services.attachments",
    "app.services.auth",
    "app.services.calendar",
    "app.services.calendar_nudges",
    "app.services.chat",
    "app.services.chats",
    "app.services.chemistry",
    "app.services.email.context",
    "app.services.email.fence",
    "app.services.email.sender_templates",
    "app.services.email.triage",
    "app.services.export_service",
    "app.services.google_integrations",
    "app.services.home",
    "app.services.images",
    "app.services.link_preview",
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
    "app.services.office_text",
    "app.services.physics",
    "app.services.plan",
    "app.services.product_analytics",
    "app.services.profile",
    "app.services.revenuecat_webhook",
    "app.services.search",
    "app.services.settings_intent",
    "app.services.settings_proposal",
    "app.services.speech",
    "app.services.subscription",
    "app.services.suggestion_generation",
    "app.services.sympy_executor",
    "app.services.todos",
    "app.services.tokens",
    "app.services.tool_loop",
    "app.services.transcript_validation",
    "app.services.web_search",
    "app.services.web_session",
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


def _module_name(path: Path) -> str:
    parts = path.relative_to(APP_ROOT.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _load_time_imports(nodes: Iterable[ast.AST]) -> list[ast.Import | ast.ImportFrom]:
    """Imports that run when the module loads: not in a function or ``if TYPE_CHECKING``."""
    found: list[ast.Import | ast.ImportFrom] = []
    for node in nodes:
        if isinstance(node, ast.Import | ast.ImportFrom):
            found.append(node)
        elif isinstance(node, ast.If) and _is_type_checking(node.test):
            found.extend(_load_time_imports(node.orelse))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        elif isinstance(node, ast.stmt | ast.excepthandler | ast.match_case):
            # A block's statements, a class body's too; an expression holds no import.
            found.extend(_load_time_imports(ast.iter_child_nodes(node)))
    return found


@cache
def _module_imports(*, load_time: bool) -> dict[str, set[str]]:
    """Production module -> every module name its imports name, made absolute.

    ``from pkg import name`` names ``pkg`` and ``pkg.name``; a package is its ``__init__``.
    With ``load_time`` only imports that run when the module loads count: deferring an
    import into a function is the accepted way to break a load-order cycle.
    """
    imports: dict[str, set[str]] = {}
    for path in _production_python():
        name = _module_name(path)
        package = name if path.name == "__init__.py" else name.rpartition(".")[0]
        tree = ast.parse(path.read_text(), filename=str(path))
        nodes = (
            _load_time_imports(tree.body)
            if load_time
            else [node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)]
        )
        targets: set[str] = set()
        for node in nodes:
            if isinstance(node, ast.Import):
                targets.update(alias.name for alias in node.names)
                continue
            base = node.module or ""
            if node.level:
                anchor = package.rsplit(".", node.level - 1)[0]
                base = f"{anchor}.{base}" if base else anchor
            targets.add(base)
            targets.update(f"{base}.{alias.name}" for alias in node.names)
        imports[name] = targets
    return imports


def _import_graph(imports: dict[str, set[str]]) -> dict[str, set[str]]:
    """Each production module -> the production modules it imports."""
    return {name: (targets & imports.keys()) - {name} for name, targets in imports.items()}


def _import_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Strongly connected components with more than one module (iterative Tarjan)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cycles: list[list[str]] = []
    for root in sorted(graph):
        if root in index:
            continue
        work = [(root, iter(sorted(graph[root])))]
        index[root] = low[root] = len(index)
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            child = next(children, None)
            if child is None:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[node])
                if low[node] == index[node]:
                    component: list[str] = []
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        component.append(member)
                        if member == node:
                            break
                    if len(component) > 1:
                        cycles.append(sorted(component))
            elif child not in index:
                index[child] = low[child] = len(index)
                stack.append(child)
                on_stack.add(child)
                work.append((child, iter(sorted(graph[child]))))
            elif child in on_stack:
                low[node] = min(low[node], index[child])
    return cycles


# What talks to a database, a cache, the network or the web framework. An ``app.core``
# module that wraps one (``redis_lock``, ``jobs``) is caught by the import it makes.
INFRASTRUCTURE: tuple[str, ...] = (
    "fastapi",
    "httpx",
    "litellm",
    "redis",
    "sqlalchemy",
    "starlette",
    "app.core.db",
    "app.core.redis",
    "app.gateways",
    "app.models.orm",
    "app.repositories",
)


def _infrastructure(names: Iterable[str]) -> list[str]:
    """The ``INFRASTRUCTURE`` roots these module names fall under."""
    return [
        root
        for root in INFRASTRUCTURE
        if any(name == root or name.startswith(f"{root}.") for name in names)
    ]


def _infrastructure_reached(packages: tuple[str, ...]) -> list[str]:
    """Each infrastructure import the packages reach, with the chain of modules to it.

    Every import counts, deferred and ``TYPE_CHECKING`` ones too: calling the function
    that holds a deferred import loads it.
    """
    imports = _module_imports(load_time=False)
    graph = _import_graph(imports)
    via: dict[str, str | None] = {
        name: None
        for name in sorted(graph)
        if any(name == package or name.startswith(f"{package}.") for package in packages)
    }
    queue = deque(via)
    while queue:
        name = queue.popleft()
        for child in sorted(graph[name]):
            if child not in via and not _infrastructure([child]):
                via[child] = name
                queue.append(child)
    violations: list[str] = []
    for name in via:
        reached = _infrastructure(imports[name])
        if not reached:
            continue
        chain = [name]
        while (step := via[chain[-1]]) is not None:
            chain.append(step)
        violations.append(f"{' -> '.join(reversed(chain))} imports {', '.join(reached)}")
    return violations


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
            if parts[1] in _PUBLIC_MODULE_TAILS:
                continue
            # A package may declare submodules public (``_MODULE_EXPORTS``,
            # dotted for nested ones such as ``tools.extract``).
            if ".".join(parts[1:]) not in _package_public_names(other):
                violations.append(f"{label} imports {module_name}")
    return violations
