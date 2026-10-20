"""Names a production module re-exports (imports from elsewhere and lists in __all__ or binds
`as same-name`) that no other file reads through that module.

Readers: `from <mod> import N`, `<alias>.N` where alias is <mod> imported as a module, a
"<mod>.N" string (patch target), or lazy _EXPORTS mapping. Source parsing only.

Usage: python -I reexports.py /home/user/recall-audit/apps/api
"""

from __future__ import annotations

import ast
import os
import re
import sys
from collections import defaultdict

API = sys.argv[1]
APP = os.path.join(API, "app")
mods: dict[str, str] = {}
for dp, _d, fs in os.walk(APP):
    if "__pycache__" in dp:
        continue
    for f in fs:
        if f.endswith(".py"):
            p = os.path.join(dp, f)
            parts = os.path.relpath(p, API)[:-3].split(os.sep)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            mods[".".join(parts)] = p


def resolve_from(cur: str, is_pkg: bool, level: int, module: str | None) -> str:
    if level == 0:
        return module or ""
    base = cur.split(".")
    if not is_pkg:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    return ".".join(base + (module.split(".") if module else []))


reexp: dict[str, dict[str, int]] = {}
trees = {m: ast.parse(open(p, encoding="utf-8").read()) for m, p in mods.items()}
for m, t in trees.items():
    if m.startswith("app.tests"):
        continue
    is_pkg = mods[m].endswith("__init__.py")
    all_names: set[str] = set()
    for node in t.body:
        if isinstance(node, ast.Assign) and any(isinstance(x, ast.Name) and x.id == "__all__" for x in node.targets):
            try:
                all_names = set(ast.literal_eval(node.value))
            except Exception:
                pass
    found: dict[str, int] = {}
    for node in t.body:
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                local = a.asname or a.name
                if (a.asname and a.asname == a.name) or local in all_names:
                    base = resolve_from(m, is_pkg, node.level, node.module)
                    if f"{base}.{a.name}" in mods:
                        continue  # submodule re-export, skip
                    found[local] = node.lineno
    if found:
        reexp[m] = found

readers: dict[tuple[str, str], set[str]] = defaultdict(set)
for m, t in trees.items():
    is_pkg = mods[m].endswith("__init__.py")
    aliases: dict[str, str] = {}
    for node in ast.walk(t):
        if isinstance(node, ast.ImportFrom):
            base = resolve_from(m, is_pkg, node.level, node.module)
            for a in node.names:
                if base in reexp and a.name in reexp[base]:
                    readers[(base, a.name)].add(m)
                sub = f"{base}.{a.name}"
                if sub in reexp:
                    aliases[a.asname or a.name] = sub
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name in reexp and a.asname:
                    aliases[a.asname] = a.name
    for node in ast.walk(t):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases:
            target = aliases[node.value.id]
            if node.attr in reexp[target]:
                readers[(target, node.attr)].add(m)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            mm = re.fullmatch(r"(app(?:\.\w+)+)\.(\w+)", node.value)
            if mm and mm.group(1) in reexp and mm.group(2) in reexp[mm.group(1)]:
                readers[(mm.group(1), mm.group(2))].add(m)
    # lazy _EXPORTS tables pointing at a re-export
    for node in t.body:
        if isinstance(node, ast.Assign) and any(isinstance(x, ast.Name) and x.id == "_EXPORTS" for x in node.targets):
            try:
                table = ast.literal_eval(node.value)
            except Exception:
                continue
            for _k, v in table.items():
                if isinstance(v, tuple):
                    tgt = f"{m}.{v[0]}"
                    if tgt in reexp and v[1] in reexp[tgt]:
                        readers[(tgt, v[1])].add(m + "#lazy")

summary = []
for m, names in sorted(reexp.items()):
    unread = [n for n in names if not readers.get((m, n))]
    test_only = [n for n in names if readers.get((m, n)) and all(r.startswith("app.tests") for r in readers[(m, n)])]
    if unread or test_only:
        summary.append((len(unread) + len(test_only), m, len(names), unread, test_only))
for total, m, n, unread, test_only in sorted(summary, reverse=True):
    print(f"{os.path.relpath(mods[m], API)}\treexports={n}\tunread={len(unread)} {sorted(unread)}\ttest_only={len(test_only)} {sorted(test_only)}")
