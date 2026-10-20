"""Read-only: imports of _private names across owners (module X importing _name from module Y,
or services/background/etc importing a module's _name; also services importing another services file's _name)."""
import ast, sys
from pathlib import Path
from collections import Counter
APP=Path(sys.argv[1])
def owner(mod):
    p=mod.split(".")
    if len(p)>=3 and p[1]=="modules": return "modules."+p[2]
    if len(p)>=3 and p[1]=="services": return "services."+p[2]
    return ".".join(p[:2])
def module_name(path):
    parts=path.relative_to(APP.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1]=="__init__" else parts)
rows=[]
for p in sorted(APP.rglob("*.py")):
    rel=p.relative_to(APP)
    if "__pycache__" in p.parts: continue
    is_test="tests" in rel.parts
    me=module_name(p)
    t=ast.parse(p.read_text())
    for n in ast.walk(t):
        if isinstance(n,ast.ImportFrom) and n.module and n.module.startswith("app.") and n.level==0:
            for a in n.names:
                if a.name.startswith("_") and not a.name.startswith("__"):
                    if is_test:
                        rows.append(("test",str(rel),n.lineno,n.module,a.name))
                    elif owner(n.module)!=owner(me):
                        rows.append(("cross",str(rel),n.lineno,n.module,a.name))
c=Counter(r[0] for r in rows)
print(c)
for r in rows:
    if r[0]=="cross": print(f"  {r[1]}:{r[2]} from {r[3]} import {r[4]}")
tc=Counter(r[3] for r in rows if r[0]=="test")
print("tests importing private names: top targets")
for k,v in tc.most_common(15): print(f"  {v:4d} {k}")
