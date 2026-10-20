"""Read-only: for each app.services.<x> (root file or package), which owners import it (all imports)."""
import ast, sys
from pathlib import Path
from collections import defaultdict
APP=Path(sys.argv[1]).resolve()
def module_name(path):
    parts=path.relative_to(APP.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1]=="__init__" else parts)
def owner(mod):
    p=mod.split(".")
    if len(p)>=3 and p[1] in ("modules","services"): return f"{p[1]}.{p[2]}"
    return ".".join(p[:2])
files=[p for p in APP.rglob("*.py") if "tests" not in p.relative_to(APP).parts and "__pycache__" not in p.parts]
cons=defaultdict(lambda: defaultdict(int))
lines=defaultdict(int)
for p in files:
    me=module_name(p); pkg=me if p.name=="__init__.py" else me.rpartition(".")[0]
    t=ast.parse(p.read_text())
    if me.startswith("app.services."):
        lines[owner(me)]+=len(p.read_text().splitlines())
    for n in ast.walk(t):
        tg=[]
        if isinstance(n,ast.Import): tg=[a.name for a in n.names]
        elif isinstance(n,ast.ImportFrom):
            base=n.module or ""
            if n.level:
                anchor=pkg.rsplit(".",n.level-1)[0]; base=f"{anchor}.{base}" if base else anchor
            tg=[base]+[f"{base}.{a.name}" for a in n.names]
        seen=set()
        for x in tg:
            if x.startswith("app.services.") :
                o=owner(x)
                if o!=owner(me) and o not in seen and o.count(".")==1:
                    seen.add(o); cons[o][owner(me)]+=1
for s in sorted(set(lines)|set(cons)):
    c=cons.get(s,{})
    mods=sorted(c)
    tag="SINGLE-CONSUMER" if len(mods)==1 else ("UNUSED" if not mods else "")
    print(f"{s:42s} {lines.get(s,0):5d} lines  consumers={len(mods):2d} {tag} {', '.join(m.replace('app.','') for m in mods)}")
