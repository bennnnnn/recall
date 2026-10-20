import ast, sys
from pathlib import Path
APP=Path(sys.argv[1])
init=APP/"models/schemas/__init__.py"
reexp={}
for n in ast.parse(init.read_text()).body:
    if isinstance(n,ast.ImportFrom) and n.module and n.module.startswith("app.modules."):
        for a in n.names: reexp[a.name]=n.module
print("module re-exports in models/schemas/__init__.py:", len(reexp))
for p in sorted(APP.rglob("*.py")):
    if "__pycache__" in p.parts: continue
    t=ast.parse(p.read_text())
    for n in ast.walk(t):
        if isinstance(n,ast.ImportFrom) and n.module=="app.models.schemas":
            hit=[a.name for a in n.names if a.name in reexp]
            if hit: print(f"  {p.relative_to(APP)}:{n.lineno} {hit}")
