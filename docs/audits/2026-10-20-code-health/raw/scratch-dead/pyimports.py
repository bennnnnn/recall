"""Build the API import graph (production vs tests) by parsing source only.

Usage: python -I pyimports.py /home/user/recall-audit/apps/api > out.json
Writes JSON: {module: {"prod": [importers], "test": [importers], "strings_prod": [...], "strings_test": [...]}}
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys

ROOT = sys.argv[1]
APP = os.path.join(ROOT, "app")

modules: dict[str, str] = {}
for dirpath, _dirs, files in os.walk(APP):
    if "__pycache__" in dirpath:
        continue
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(dirpath, f)
        rel = os.path.relpath(path, ROOT)[:-3]
        parts = rel.split(os.sep)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules[".".join(parts)] = path

# Alembic env + versions also import app code
ALEMBIC = os.path.join(ROOT, "alembic")
extra_files = []
for dirpath, _dirs, files in os.walk(ALEMBIC):
    for f in files:
        if f.endswith(".py"):
            extra_files.append(os.path.join(dirpath, f))

lazy_exports: dict[str, dict[str, str]] = {}
special_all_surface = {"app.modules.memory": "app.modules.memory.surface"}


def parse(path: str) -> ast.Module | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return ast.parse(fh.read(), filename=path)
    except SyntaxError:
        return None


# Gather _EXPORTS tables
for mod, path in modules.items():
    if not path.endswith("__init__.py"):
        continue
    tree = parse(path)
    if tree is None:
        continue
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_EXPORTS" for t in node.targets
        ):
            try:
                val = ast.literal_eval(node.value)
            except Exception:
                continue
            table = {}
            for k, v in val.items():
                if isinstance(v, tuple):
                    table[k] = f"{mod}.{v[0]}"
                elif isinstance(v, str):
                    table[k] = f"{mod}.{v.lstrip('.')}"
            lazy_exports[mod] = table


def is_test(mod_or_path: str) -> bool:
    return "/tests/" in mod_or_path or ".tests." in mod_or_path or mod_or_path.endswith(".tests")


def resolve_from(current: str, is_pkg: bool, level: int, module: str | None) -> str:
    if level == 0:
        return module or ""
    base = current.split(".")
    if not is_pkg:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    if module:
        return ".".join(base + module.split("."))
    return ".".join(base)


def targets_for(current: str, path: str, tree: ast.Module) -> tuple[set[str], set[str]]:
    is_pkg = path.endswith("__init__.py")
    out: set[str] = set()
    strings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                name = a.name
                # import a.b.c registers a, a.b, a.b.c
                parts = name.split(".")
                for i in range(1, len(parts) + 1):
                    cand = ".".join(parts[:i])
                    if cand in modules:
                        out.add(cand)
        elif isinstance(node, ast.ImportFrom):
            base = resolve_from(current, is_pkg, node.level, node.module)
            if base in modules:
                out.add(base)
            # parents too (package __init__ executes)
            parts = base.split(".")
            for i in range(1, len(parts)):
                cand = ".".join(parts[:i])
                if cand in modules:
                    out.add(cand)
            for a in node.names:
                sub = f"{base}.{a.name}"
                if sub in modules:
                    out.add(sub)
                elif base in lazy_exports and a.name in lazy_exports[base]:
                    tgt = lazy_exports[base][a.name]
                    if tgt in modules:
                        out.add(tgt)
                elif base in special_all_surface:
                    out.add(special_all_surface[base])
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value
            if re.fullmatch(r"app(\.\w+)+(:\w+)?", s):
                s2 = s.split(":")[0]
                parts = s2.split(".")
                # longest prefix that is a module
                for i in range(len(parts), 0, -1):
                    cand = ".".join(parts[:i])
                    if cand in modules:
                        strings.add(cand)
                        break
        elif isinstance(node, ast.Attribute):
            pass
    return out, strings


graph: dict[str, dict[str, set[str]]] = {
    m: {"prod": set(), "test": set(), "strings_prod": set(), "strings_test": set()} for m in modules
}
for mod, path in list(modules.items()) + [(f"alembic:{p}", p) for p in extra_files]:
    tree = parse(path)
    if tree is None:
        continue
    cur = mod if not mod.startswith("alembic:") else "alembic"
    tgts, strs = targets_for(cur, path, tree)
    kind = "test" if is_test(path) else "prod"
    for t in tgts:
        if t == mod:
            continue
        graph[t][kind].add(mod)
    for s in strs:
        if s == mod:
            continue
        graph[s]["strings_" + kind].add(mod)

json.dump(
    {m: {k: sorted(v) for k, v in d.items()} for m, d in graph.items()},
    sys.stdout,
    indent=1,
    sort_keys=True,
)
