"""Find module-level mutable containers (dict/set/list/defaultdict/OrderedDict/deque)
that are mutated inside functions (subscript assignment, .add/.append/.setdefault/...).

Read-only: parses source with ast. Usage: python3 -I module_state.py <app_dir>
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

CONTAINER_CALLS = {"dict", "set", "list", "defaultdict", "OrderedDict", "deque", "WeakValueDictionary", "WeakKeyDictionary", "WeakSet", "Counter"}
MUTATORS = {"add", "append", "setdefault", "update", "extend", "insert", "appendleft", "__setitem__"}
REMOVERS = {"pop", "discard", "remove", "clear", "popitem", "popleft", "difference_update"}


def container_kind(value: ast.AST | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, ast.Dict):
        return "dict"
    if isinstance(value, ast.Set):
        return "set"
    if isinstance(value, ast.List):
        return "list"
    if isinstance(value, ast.Call):
        func = value.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in CONTAINER_CALLS:
            return name
    return None


def main(root: str) -> None:
    base = Path(root)
    for path in sorted(base.rglob("*.py")):
        if "/tests/" in str(path):
            continue
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            continue
        names: dict[str, tuple[int, str]] = {}
        for node in tree.body:
            targets: list[ast.AST] = []
            value = None
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            kind = container_kind(value)
            if kind is None:
                continue
            for t in targets:
                if isinstance(t, ast.Name):
                    names[t.id] = (node.lineno, kind)
        if not names:
            continue
        adds: dict[str, list[int]] = {n: [] for n in names}
        removes: dict[str, list[int]] = {n: [] for n in names}
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    obj = node.func.value
                    if isinstance(obj, ast.Name) and obj.id in names:
                        if node.func.attr in MUTATORS:
                            adds[obj.id].append(node.lineno)
                        elif node.func.attr in REMOVERS:
                            removes[obj.id].append(node.lineno)
                elif isinstance(node, (ast.Assign, ast.AugAssign)):
                    tgts = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for t in tgts:
                        if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id in names:
                            adds[t.value.id].append(node.lineno)
                elif isinstance(node, ast.Delete):
                    for t in node.targets:
                        if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id in names:
                            removes[t.value.id].append(node.lineno)
        rel = path.relative_to(base.parent.parent.parent)
        for n, (line, kind) in names.items():
            if adds[n]:
                print(f"{rel}:{line}: {n} ({kind}) adds@{adds[n]} removes@{removes[n]}")


if __name__ == "__main__":
    main(sys.argv[1])
