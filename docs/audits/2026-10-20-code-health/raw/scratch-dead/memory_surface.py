"""For every name bound in app/modules/memory/surface.py: production readers vs test readers.

Production reads a surface name N when:
  - memory submodules call `seams.N` (the package object passed as `seams`), or
  - another production module does `from app.modules.memory import N`, or reads `<alias>.N`
    where <alias> is the memory package (imported as a module object).
Tests read it when they import it from the package, patch "app.modules.memory.N", or
patch.object/setattr the package alias with "N".

Usage: python -I memory_surface.py /home/user/recall-audit/apps/api
"""

from __future__ import annotations

import ast
import os
import re
import sys
from collections import defaultdict

API = sys.argv[1]
APP = os.path.join(API, "app")
SURFACE = os.path.join(APP, "modules/memory/surface.py")

tree = ast.parse(open(SURFACE, encoding="utf-8").read())
bound: dict[str, str] = {}
for node in tree.body:
    if isinstance(node, ast.ImportFrom):
        for a in node.names:
            if a.asname and a.asname == a.name:
                bound[a.name] = f"re-export from {node.module}"
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]
        forwards = (
            len(body) == 1
            and isinstance(body[0], (ast.Return, ast.Expr))
            and body[0].value is not None
            and isinstance(
                body[0].value.value if isinstance(body[0].value, ast.Await) else body[0].value,
                ast.Call,
            )
        )
        bound[node.name] = "forwarding wrapper" if forwards else "function"
    elif isinstance(node, ast.ClassDef):
        bound[node.name] = "class"

prod_reads: dict[str, set[str]] = defaultdict(set)
test_reads: dict[str, set[str]] = defaultdict(set)

for dirpath, _d, fs in os.walk(APP):
    if "__pycache__" in dirpath:
        continue
    for f in fs:
        if not f.endswith(".py"):
            continue
        path = os.path.join(dirpath, f)
        if path == SURFACE:
            continue
        rel = os.path.relpath(path, API)
        src = open(path, encoding="utf-8").read()
        is_test = "/tests/" in path
        t = ast.parse(src)
        aliases = set()
        for node in ast.walk(t):
            if isinstance(node, ast.ImportFrom) and node.module == "app.modules" and node.level == 0:
                for a in node.names:
                    if a.name == "memory":
                        aliases.add(a.asname or a.name)
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name == "app.modules.memory" and a.asname:
                        aliases.add(a.asname)
            if isinstance(node, ast.ImportFrom) and node.module == "app.modules.memory":
                for a in node.names:
                    if a.name in bound:
                        (test_reads if is_test else prod_reads)[a.name].add(rel)
        in_memory_pkg = "/modules/memory/" in path and not is_test
        for node in ast.walk(t):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.attr in bound and (
                    node.value.id in aliases or (in_memory_pkg and node.value.id == "seams")
                ):
                    (test_reads if is_test else prod_reads)[node.attr].add(rel)
        if is_test:
            for m in re.finditer(r"app\.modules\.memory\.(\w+)", src):
                if m.group(1) in bound:
                    test_reads[m.group(1)].add(rel)
            for alias in aliases:
                for m in re.finditer(rf"(?:patch\.object|setattr)\(\s*{alias}\s*,\s*[\"'](\w+)", src):
                    if m.group(1) in bound:
                        test_reads[m.group(1)].add(rel)

rows = []
for name, kind in bound.items():
    p, tt = prod_reads.get(name, set()), test_reads.get(name, set())
    status = "PROD" if p else ("TEST-ONLY" if tt else "UNREAD")
    rows.append((status, kind, name, len(p), len(tt), sorted(p)[:3]))
rows.sort()
for r in rows:
    print("\t".join(str(x) for x in r))
print(f"# bound={len(bound)} prod={sum(1 for r in rows if r[0]=='PROD')} test_only={sum(1 for r in rows if r[0]=='TEST-ONLY')} unread={sum(1 for r in rows if r[0]=='UNREAD')} forwarding={sum(1 for r in rows if r[1]=='forwarding wrapper')}")
