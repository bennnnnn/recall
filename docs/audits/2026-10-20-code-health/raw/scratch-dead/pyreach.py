"""Import-aware reachability of top-level defs in API production code (source parsing only).

A top-level def (function, class, constant) is live when production module-level code, a
root decorator, or another live def references it through a resolved name: a local name, a
`from X import N` binding (followed through package re-exports and lazy `_EXPORTS`), or a
`module_alias.N` attribute. Whatever is not reached is reported, with how many test files
reference it (test-only production code).

Usage: python -I pyreach.py /home/user/recall-audit/apps/api
"""

from __future__ import annotations

import ast
import os
import re
import sys
from collections import defaultdict

ROOT = sys.argv[1]
APP = os.path.join(ROOT, "app")

modules: dict[str, str] = {}
for dirpath, _dirs, fs in os.walk(APP):
    if "__pycache__" in dirpath:
        continue
    for f in fs:
        if f.endswith(".py"):
            path = os.path.join(dirpath, f)
            rel = os.path.relpath(path, ROOT)[:-3]
            parts = rel.split(os.sep)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            modules[".".join(parts)] = path
alembic_files = []
for dirpath, _dirs, fs in os.walk(os.path.join(ROOT, "alembic")):
    for f in fs:
        if f.endswith(".py"):
            alembic_files.append(os.path.join(dirpath, f))


def is_test_mod(m: str) -> bool:
    return m.startswith("app.tests")


trees: dict[str, ast.Module] = {}
for m, p in modules.items():
    with open(p, encoding="utf-8") as fh:
        trees[m] = ast.parse(fh.read(), filename=p)
for i, p in enumerate(alembic_files):
    with open(p, encoding="utf-8") as fh:
        trees[f"alembic.f{i}"] = ast.parse(fh.read(), filename=p)
    modules[f"alembic.f{i}"] = p


def resolve_from(current: str, is_pkg: bool, level: int, module: str | None) -> str:
    if level == 0:
        return module or ""
    base = current.split(".")
    if not is_pkg:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    return ".".join(base + (module.split(".") if module else []))


# Per module: top-level defs, import bindings, module aliases, lazy exports
defs: dict[str, dict[str, ast.AST]] = defaultdict(dict)
bindings: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)  # local -> (module, name)
mod_alias: dict[str, dict[str, str]] = defaultdict(dict)  # local -> module
lazy: dict[str, dict[str, tuple[str, str]]] = {}
star_from: dict[str, list[str]] = defaultdict(list)

for m, tree in trees.items():
    is_pkg = modules[m].endswith("__init__.py")
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs[m][node.name] = node
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    defs[m][t.id] = node
                    if t.id == "_EXPORTS":
                        try:
                            val = ast.literal_eval(node.value)
                            lazy[m] = {
                                k: (f"{m}.{v[0]}", v[1]) for k, v in val.items() if isinstance(v, tuple)
                            }
                        except Exception:
                            pass
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defs[m][node.target.id] = node
        elif isinstance(node, ast.TypeAlias):
            defs[m][node.name.id] = node
    # imports anywhere in the module (function-local imports included)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    mod_alias[m][a.asname] = a.name
                else:
                    mod_alias[m][a.name.split(".")[0]] = a.name.split(".")[0]
                    # full dotted chains handled in attribute resolution
        elif isinstance(node, ast.ImportFrom):
            base = resolve_from(m if not m.startswith("alembic") else "alembic", is_pkg, node.level, node.module)
            for a in node.names:
                local = a.asname or a.name
                if a.name == "*":
                    star_from[m].append(base)
                    continue
                if f"{base}.{a.name}" in modules:
                    mod_alias[m][local] = f"{base}.{a.name}"
                else:
                    bindings[m][local] = (base, a.name)

MEMORY_SURFACE = ("app.modules.memory", "app.modules.memory.surface")


def resolve(mod: str, name: str, depth: int = 0) -> tuple[str, str] | None:
    if depth > 12:
        return None
    if mod == MEMORY_SURFACE[0] and name not in defs[mod]:
        return resolve(MEMORY_SURFACE[1], name, depth + 1)
    if name in defs.get(mod, {}):
        return (mod, name)
    if name in bindings.get(mod, {}):
        b = bindings[mod][name]
        return resolve(b[0], b[1], depth + 1)
    if mod in lazy and name in lazy[mod]:
        t = lazy[mod][name]
        return resolve(t[0], t[1], depth + 1)
    for s in star_from.get(mod, []):
        r = resolve(s, name, depth + 1)
        if r:
            return r
    return None


def dotted(node: ast.AST) -> str | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


ROOT_DECOS = (
    "router.",
    "app.",
    "field_validator",
    "model_validator",
    "validator",
    "computed_field",
    "field_serializer",
    "model_serializer",
    "fixture",
    "register",
    "listens_for",
    "event.",
    "lru_cache",
)


def refs_in(m: str, node: ast.AST) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    attr_values = {id(s.value) for s in ast.walk(node) if isinstance(s, ast.Attribute)}
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            n = sub.id
            if n in defs[m]:
                out.add((m, n))
            r = resolve(m, n) if n in bindings[m] else None
            if r:
                out.add(r)
            if n in mod_alias[m] and id(sub) not in attr_values:
                tm = mod_alias[m][n]
                if tm != MEMORY_SURFACE[0]:
                    out.add((tm, "*"))
            if n in bindings[m] and id(sub) not in attr_values:
                b = bindings[m][n]
                cand = f"{b[0]}.{b[1]}"
                if cand in modules:
                    out.add((cand, "*"))
        elif isinstance(sub, ast.Attribute):
            if m.startswith("app.modules.memory") and isinstance(sub.value, ast.Name) and sub.value.id == "seams":
                r = resolve(MEMORY_SURFACE[1], sub.attr)
                if r:
                    out.add(r)
            d = dotted(sub)
            if not d:
                continue
            parts = d.split(".")
            # find longest prefix that maps to a module
            for i in range(len(parts) - 1, 0, -1):
                head = parts[0]
                if head in mod_alias[m]:
                    target_mod = ".".join([mod_alias[m][head]] + parts[1:i])
                elif ".".join(parts[:i]) in modules:
                    target_mod = ".".join(parts[:i])
                else:
                    continue
                if target_mod in modules or target_mod in lazy:
                    r = resolve(target_mod, parts[i])
                    if r:
                        out.add(r)
                    break
        elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            s = sub.value
            if s in modules and isinstance(sub, ast.Constant) and not s.startswith(MEMORY_SURFACE[0]):
                out.add((s, "*"))
            mm = re.fullmatch(r"(app(?:\.\w+)+)[.:](\w+)", s)
            if mm:
                for cand_mod, cand_name in ((mm.group(1), mm.group(2)),):
                    if cand_mod in modules:
                        r = resolve(cand_mod, cand_name)
                        if r:
                            out.add(r)
            elif re.fullmatch(r"\w+", s):
                # getattr(module, "name") or registries by name: conservative, any module
                for dm, names in defs.items():
                    if s in names and not is_test_mod(dm):
                        out.add((dm, s))
    return out


# Edges
edges: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
roots: set[tuple[str, str]] = set()
test_refs: dict[tuple[str, str], set[str]] = defaultdict(set)

for m, tree in trees.items():
    test = is_test_mod(m)
    for node in tree.body:
        owner = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            owner = (m, node.name)
            decos = [ast.unparse(d) for d in node.decorator_list]
            if not test and any(any(k in d for k in ROOT_DECOS) for d in decos):
                roots.add(owner)
            # decorators and default args are evaluated at module level
            for d in node.decorator_list:
                for r in refs_in(m, d):
                    if test:
                        test_refs[r].add(m)
                    else:
                        roots.add(r)
            if isinstance(node, ast.ClassDef):
                for b in node.bases + [k.value for k in node.keywords]:
                    for r in refs_in(m, b):
                        if not test:
                            edges[owner].add(r)
                        else:
                            test_refs[r].add(m)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [t.id for t in targets if isinstance(t, ast.Name)]
            if names and names[0] not in ("__all__",):
                owner = (m, names[0])
            elif names and names[0] == "__all__":
                continue  # an export list is not a use
        if owner is None:
            # module-level statement: root references
            for r in refs_in(m, node):
                if test:
                    test_refs[r].add(m)
                else:
                    roots.add(r)
            continue
        for r in refs_in(m, node):
            if r == owner:
                continue
            if test:
                test_refs[r].add(m)
            else:
                edges[owner].add(r)

# Entry-point roots
for m in ("app.main", "app.worker_main", "app.worker_health", "app.process_bootstrap"):
    for n in defs.get(m, {}):
        roots.add((m, n))

live: set[tuple[str, str]] = set()
stack = [r for r in roots if not is_test_mod(r[0])]
while stack:
    cur = stack.pop()
    if cur in live:
        continue
    live.add(cur)
    if cur[1] == "*":
        stack.extend((cur[0], n) for n in defs.get(cur[0], {}))
        for b in ([] if cur[0] == MEMORY_SURFACE[1] else bindings.get(cur[0], {})):
            r = resolve(cur[0], b)
            if r:
                stack.append(r)
        continue
    stack.extend(edges.get(cur, ()))

rows = []
for m, names in defs.items():
    if is_test_mod(m) or m.startswith("alembic"):
        continue
    for n, node in names.items():
        if (m, n) in live:
            continue
        if n.startswith("__") and n.endswith("__"):
            continue
        if n in ("router", "logger", "log", "_log", "_logger", "_EXPORTS", "_MODULE_EXPORTS", "LOGGER"):
            continue
        kind = type(node).__name__
        lines = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1
        rows.append((os.path.relpath(modules[m], ROOT), node.lineno, kind, n, lines, len(test_refs.get((m, n), set()) | test_refs.get((m, "*"), set()))))
rows.sort()
for r in rows:
    print(f"{r[0]}:{r[1]}\t{r[2]}\t{r[3]}\tlines={r[4]}\ttest_files={r[5]}")
print(f"# defs={sum(len(v) for k, v in defs.items() if not is_test_mod(k))} unreached={len(rows)}", file=sys.stderr)
