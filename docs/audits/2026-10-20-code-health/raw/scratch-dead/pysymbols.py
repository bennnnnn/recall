"""Top-level and class-member symbols in API production code with no production reference.

Parses source only. A reference is any NAME token or identifier inside a string literal
(getattr / patch targets / __all__), in any .py file under app/ or alembic/, other than the
defining occurrence itself.

Usage: python -I pysymbols.py /home/user/recall-audit/apps/api
"""

from __future__ import annotations

import ast
import io
import os
import re
import sys
import tokenize
from collections import Counter, defaultdict

ROOT = sys.argv[1]
files: list[str] = []
for base in ("app", "alembic"):
    for dirpath, _dirs, fs in os.walk(os.path.join(ROOT, base)):
        if "__pycache__" in dirpath:
            continue
        for f in fs:
            if f.endswith(".py"):
                files.append(os.path.join(dirpath, f))


def is_test(path: str) -> bool:
    return "/tests/" in path


prod_counts: Counter[str] = Counter()
test_counts: Counter[str] = Counter()
per_file_counts: dict[str, Counter[str]] = {}
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

for path in files:
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    c: Counter[str] = Counter()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.NAME:
                c[tok.string] += 1
            elif tok.type == tokenize.STRING:
                for m in IDENT.findall(tok.string):
                    c[m] += 1
            elif tok.type == getattr(tokenize, "FSTRING_MIDDLE", -1):
                for m in IDENT.findall(tok.string):
                    c[m] += 1
    except (tokenize.TokenError, IndentationError, SyntaxError):
        continue
    per_file_counts[path] = c
    (test_counts if is_test(path) else prod_counts).update(c)

SKIP_DECORATORS = (
    "router.",
    "app.",
    "field_validator",
    "model_validator",
    "validator",
    "root_validator",
    "computed_field",
    "field_serializer",
    "model_serializer",
    "fixture",
    "register",
    "listens_for",
    "property",
    "cached_property",
    "overload",
    "classmethod",
    "staticmethod",
    "abstractmethod",
    "setter",
)

rows = []
for path in files:
    if is_test(path) or "/alembic/" in path:
        continue
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue
    defs: list[tuple[str, int, str, str]] = []  # name, line, kind, owner

    def deco_names(node: ast.AST) -> list[str]:
        out = []
        for d in getattr(node, "decorator_list", []):
            out.append(ast.unparse(d))
        return out

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.append((node.name, node.lineno, "func", "", deco_names(node)))
        elif isinstance(node, ast.ClassDef):
            defs.append((node.name, node.lineno, "class", "", deco_names(node)))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if sub.name.startswith("__"):
                        continue
                    defs.append((sub.name, sub.lineno, "method", node.name, deco_names(sub)))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    defs.append((t.id, node.lineno, "const", "", []))
    for name, line, kind, owner, decos in defs:
        if name.startswith("__") and name.endswith("__"):
            continue
        if name in {"router", "logger", "log", "settings", "_log", "_logger", "LOGGER"}:
            continue
        if any(any(s in d for s in SKIP_DECORATORS) for d in decos):
            continue
        own = per_file_counts.get(path, Counter())[name]
        p = prod_counts[name] - own  # refs in other prod files
        t = test_counts[name]
        if p == 0:
            rel = os.path.relpath(path, ROOT)
            rows.append((rel, line, kind, owner, name, own, t))

rows.sort()
for rel, line, kind, owner, name, own, t in rows:
    tag = "TESTONLY" if t else "UNUSED"
    if own > 1:
        tag += "+selfuse"
    print(f"{rel}:{line}\t{kind}\t{owner + '.' if owner else ''}{name}\town={own}\ttest={t}\t{tag}")
