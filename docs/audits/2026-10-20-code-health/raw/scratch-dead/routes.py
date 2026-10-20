"""Every FastAPI route (method, full path, handler) from source, with router prefixes.

Usage: python -I routes.py /home/user/recall-audit/apps/api
Prints: METHOD\tPATH\tfile:line\thandler
"""

from __future__ import annotations

import ast
import os
import sys

API = sys.argv[1]
APP = os.path.join(API, "app")
METHODS = {"get", "post", "put", "patch", "delete", "websocket", "api_route"}

for dirpath, _d, fs in os.walk(APP):
    if "/tests" in dirpath or "__pycache__" in dirpath:
        continue
    for f in fs:
        if not f.endswith(".py"):
            continue
        path = os.path.join(dirpath, f)
        src = open(path, encoding="utf-8").read()
        if "APIRouter" not in src:
            continue
        tree = ast.parse(src)
        prefixes: dict[str, str] = {}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and ast.unparse(node.value.func).endswith("APIRouter")
            ):
                pfx = ""
                for kw in node.value.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        pfx = kw.value.value
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        prefixes[t.id] = pfx
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for d in node.decorator_list:
                if (
                    isinstance(d, ast.Call)
                    and isinstance(d.func, ast.Attribute)
                    and d.func.attr in METHODS
                    and isinstance(d.func.value, ast.Name)
                    and d.func.value.id in prefixes
                ):
                    route = d.args[0].value if d.args and isinstance(d.args[0], ast.Constant) else "?"
                    print(
                        f"{d.func.attr.upper()}\t{prefixes[d.func.value.id]}{route}\t"
                        f"{os.path.relpath(path, API)}:{node.lineno}\t{node.name}"
                    )
