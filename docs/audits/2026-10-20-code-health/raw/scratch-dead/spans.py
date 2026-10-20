"""Print start-end line spans (decorators included) of named top-level defs/classes.

Usage: python -I spans.py <repo-root> <relpath>:<name>[,<name>...] ...
"""

from __future__ import annotations

import ast
import os
import sys

ROOT = sys.argv[1]
total = 0
for arg in sys.argv[2:]:
    rel, names = arg.split(":", 1)
    wanted = set(names.split(","))
    tree = ast.parse(open(os.path.join(ROOT, rel), encoding="utf-8").read())
    for node in ast.walk(tree):
        name = getattr(node, "name", None)
        if isinstance(node, ast.Assign):
            tgt = node.targets[0]
            name = tgt.id if isinstance(tgt, ast.Name) else None
        if name in wanted and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign)):
            start = min([d.lineno for d in getattr(node, "decorator_list", [])] + [node.lineno])
            end = node.end_lineno or node.lineno
            total += end - start + 1
            print(f"{rel}:{start}-{end}\t{name}\t{end - start + 1}")
            wanted.discard(name)
    for missing in wanted:
        print(f"{rel}\t{missing}\tNOT FOUND")
print(f"# total lines {total}")
