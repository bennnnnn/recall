"""Settings fields under app/core/settings/ and where production / tests / docs read them.

A field counts as read by production when its name appears as an attribute (`.field`), in a
getattr string, or as a bare identifier anywhere in app/ outside tests and outside the settings
section that declares it. Also reports the declared default.

Usage: python -I settings_use.py /home/user/recall-audit
"""

from __future__ import annotations

import ast
import os
import re
import sys
from collections import Counter

REPO = sys.argv[1]
API = os.path.join(REPO, "apps/api")
SETTINGS_DIR = os.path.join(API, "app/core/settings")

fields: list[tuple[str, str, int, str]] = []  # (file, name, line, default)
for f in sorted(os.listdir(SETTINGS_DIR)):
    if not f.endswith(".py") or f == "__init__.py":
        continue
    path = os.path.join(SETTINGS_DIR, f)
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, ast.AnnAssign) and isinstance(sub.target, ast.Name):
                    default = ast.unparse(sub.value) if sub.value is not None else "<required>"
                    fields.append((f, sub.target.id, sub.lineno, default))

prod_attr: Counter[str] = Counter()
prod_ident: Counter[str] = Counter()
test_ident: Counter[str] = Counter()
ATTR = re.compile(r"\.([a-z_][a-z0-9_]*)")
IDENT = re.compile(r"\b([a-z_][a-z0-9_]*)\b")
for base in ("app", "alembic"):
    for dirpath, _d, fs in os.walk(os.path.join(API, base)):
        if "__pycache__" in dirpath:
            continue
        for f in fs:
            if not f.endswith(".py"):
                continue
            path = os.path.join(dirpath, f)
            text = open(path, encoding="utf-8").read()
            if "/tests/" in path:
                test_ident.update(IDENT.findall(text))
                continue
            if path.startswith(SETTINGS_DIR):
                # count only uses inside the settings package that are not declarations
                text = re.sub(r"^\s+[a-z_][a-z0-9_]*\s*:.*$", "", text, flags=re.M)
            prod_attr.update(ATTR.findall(text))
            prod_ident.update(IDENT.findall(text))

# env files / docs mention (upper-case env name)
doc_text = ""
for root, _d, fs in os.walk(REPO):
    if any(x in root for x in ("node_modules", ".git", "/tmp", "__pycache__", ".venv")):
        continue
    for f in fs:
        if f.endswith((".md", ".toml", ".example", ".yml", ".yaml", ".sh", ".env")) or f.startswith(".env"):
            try:
                doc_text += open(os.path.join(root, f), encoding="utf-8", errors="ignore").read() + "\n"
            except OSError:
                pass

for f, name, line, default in fields:
    a = prod_attr[name]
    i = prod_ident[name]
    t = test_ident[name]
    env = name.upper()
    d = len(re.findall(rf"\b{re.escape(env)}\b", doc_text))
    status = "READ" if a or i else ("TESTONLY" if t else "UNREAD")
    print(f"{status}\tapp/core/settings/{f}:{line}\t{name}\tdefault={default[:60]}\tprod_attr={a}\tprod_ident={i}\ttest={t}\tdocs={d}")
