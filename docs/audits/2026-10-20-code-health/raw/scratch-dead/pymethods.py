"""Methods of production classes whose name is never read as an attribute in production.

Name-based (like vulture): a method `m` counts as used when `.m` appears in a production file
(any object), or `m` appears in a string (getattr), or it overrides a known protocol hook.
Usage: python -I pymethods.py /home/user/recall-audit/apps/api
"""

from __future__ import annotations

import ast
import os
import re
import sys
from collections import Counter

API = sys.argv[1]
APP = os.path.join(API, "app")
attr_prod: Counter[str] = Counter()
attr_test: Counter[str] = Counter()
str_prod: Counter[str] = Counter()
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
files = []
for dirpath, _d, fs in os.walk(APP):
    if "__pycache__" in dirpath:
        continue
    for f in fs:
        if f.endswith(".py"):
            files.append(os.path.join(dirpath, f))
for path in files:
    tree = ast.parse(open(path, encoding="utf-8").read())
    test = "/tests/" in path
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            (attr_test if test else attr_prod)[node.attr] += 1
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and not test:
            for m in IDENT.findall(node.value):
                str_prod[m] += 1
        elif isinstance(node, ast.keyword) and node.arg and not test:
            str_prod[node.arg] += 1

HOOKS = {
    "handle_starttag", "handle_endtag", "handle_data", "handle_startendtag", "dispatch",
    "emit", "filter", "format", "run", "close", "aclose", "send", "receive", "process_bind_param",
    "process_result_value", "load_dialect_impl", "copy", "get", "keys", "values", "items",
    "visit_Name", "generic_visit", "model_post_init", "default", "encode", "decode",
}
for path in files:
    if "/tests/" in path:
        continue
    tree = ast.parse(open(path, encoding="utf-8").read())
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        bases = [ast.unparse(b) for b in cls.bases]
        is_protocol = any("Protocol" in b for b in bases)
        for sub in cls.body:
            if not isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = sub.name
            if name.startswith("__") or name in HOOKS or name.startswith("visit_"):
                continue
            decos = [ast.unparse(d) for d in sub.decorator_list]
            if any(
                k in d
                for d in decos
                for k in ("validator", "serializer", "computed_field", "router.", "fixture")
            ):
                continue
            used = attr_prod[name] + str_prod[name]
            if used == 0:
                print(
                    f"{os.path.relpath(path, API)}:{sub.lineno}\t{cls.name}.{name}\t"
                    f"protocol={is_protocol}\tbases={','.join(bases)}\ttest_attr={attr_test[name]}"
                )
