"""Direct writes to imported modules' attributes (or their dict/list globals) inside
API tests, outside monkeypatch/patch: `mod.X = ...`, `mod.X[k] = ...`,
`mod.X.append/clear/update(...)`. These persist after the test."""
import ast, subprocess, sys
from pathlib import Path
api = Path(sys.argv[1])
files = subprocess.run(["git", "ls-files", "app/tests"], cwd=api, capture_output=True, text=True).stdout.split()
hits = []
for rel in files:
    if not rel.endswith(".py"):
        continue
    tree = ast.parse((api / rel).read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                modules.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
            for a in node.names:
                # "from app.x import y" — y may be a module; we treat lowercase names as possible modules
                if a.name.islower():
                    modules.add(a.asname or a.name)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AugAssign):
                targets = [node.target]
            for t in targets:
                base = t
                if isinstance(base, ast.Subscript):
                    base = base.value
                if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and base.value.id in modules:
                    hits.append(f"{rel}:{node.lineno} {ast.unparse(t)[:70]}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("clear", "append", "update", "add", "pop", "setdefault", "extend", "remove", "discard"):
                v = node.func.value
                if isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and v.value.id in modules and v.attr.isupper() or (isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and v.value.id in modules and v.attr.startswith("_")):
                    hits.append(f"{rel}:{node.lineno} {ast.unparse(node)[:70]}")
print(len(hits), "direct module-state writes in tests")
for h in hits:
    print(" ", h)
