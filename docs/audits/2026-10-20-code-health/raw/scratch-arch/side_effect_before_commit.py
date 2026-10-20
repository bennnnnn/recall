"""Read-only: side effects (cache invalidation, enqueue, generation bump, push/email send)
that run BEFORE a later session.commit() in the same function body."""
import ast, sys, re
from pathlib import Path
APP=Path(sys.argv[1])
SIDE=re.compile(r"(invalidate|enqueue|bump_generation|forget_chat|publish|send_push|send_email|_invalidate|schedule_related|create_background_task)", re.I)
for p in sorted(APP.rglob("*.py")):
    rel=p.relative_to(APP)
    if "tests" in rel.parts or "__pycache__" in p.parts: continue
    t=ast.parse(p.read_text())
    for fn in ast.walk(t):
        if not isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
        side=[];commits=[]
        for n in ast.walk(fn):
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n is not fn: continue
            if isinstance(n,ast.Call):
                f=n.func
                name=f.attr if isinstance(f,ast.Attribute) else (f.id if isinstance(f,ast.Name) else "")
                if name=="commit" and not n.args: commits.append(n.lineno)
                elif SIDE.search(name or ""): side.append((n.lineno,name))
        if commits and side:
            early=[s for s in side if any(c>s[0] for c in commits)]
            if early:
                print(f"{rel}:{fn.lineno} {fn.name}: side effects {early} before commit lines {commits}")
