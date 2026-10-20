"""ORM columns and how production code touches them (source parsing only).

For each `name: Mapped[...] = mapped_column(...)` (or Column) in ORM classes, count production
references to `.name` (attribute) and `name=` (keyword) and `"name"` (string), excluding the ORM
file itself, alembic and tests. Reports columns with zero or only-export references.

Usage: python -I orm_columns.py /home/user/recall-audit/apps/api
"""

from __future__ import annotations

import ast
import os
import re
import sys
from collections import Counter, defaultdict

API = sys.argv[1]
APP = os.path.join(API, "app")

orm_files = []
for dirpath, _d, fs in os.walk(APP):
    if "/tests" in dirpath or "__pycache__" in dirpath:
        continue
    for f in fs:
        if f.endswith(".py"):
            p = os.path.join(dirpath, f)
            s = open(p, encoding="utf-8").read()
            if "mapped_column(" in s or "Column(" in s:
                orm_files.append(p)

columns = []  # (file, class, name, line)
for p in orm_files:
    tree = ast.parse(open(p, encoding="utf-8").read())
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for sub in node.body:
            if isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name) and sub.value is not None:
                src = ast.unparse(sub.value)
                if "mapped_column(" in src or "Column(" in src or "relationship(" in src:
                    columns.append((p, node.name, sub.target.id, sub.lineno, "relationship(" in src))

refs_attr: dict[str, Counter[str]] = defaultdict(Counter)
for dirpath, _d, fs in os.walk(APP):
    if "/tests" in dirpath or "__pycache__" in dirpath:
        continue
    for f in fs:
        if not f.endswith(".py"):
            continue
        p = os.path.join(dirpath, f)
        s = open(p, encoding="utf-8").read()
        for m in re.finditer(r"\.([a-z_][a-z0-9_]*)\b", s):
            refs_attr[m.group(1)][p] += 1
        for m in re.finditer(r"\b([a-z_][a-z0-9_]*)\s*=(?!=)", s):
            refs_attr[m.group(1)][p] += 1
        for m in re.finditer(r"[\"']([a-z_][a-z0-9_]*)[\"']", s):
            refs_attr[m.group(1)][p] += 1

for p, cls, name, line, is_rel in columns:
    others = {f: c for f, c in refs_attr.get(name, {}).items() if f != p}
    non_export = {f: c for f, c in others.items() if not f.endswith(("account/export.py",))}
    if len(non_export) == 0:
        rel = os.path.relpath(p, API)
        print(f"{rel}:{line}\t{cls}.{name}\trel={is_rel}\tfiles={sorted(os.path.relpath(f, API) for f in others)}")
