"""Read-only: which owners call WRITE functions of shared repositories (app.repositories.*)."""
import ast, sys, re
from pathlib import Path
from collections import defaultdict
APP=Path(sys.argv[1]).resolve()
def module_name(path):
    parts=path.relative_to(APP.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1]=="__init__" else parts)
# classify repo functions as writes: contain session.add/delete/execute(update|delete|insert)/commit/flush
WRITE=re.compile(r"session\.(add|add_all|delete|commit|flush)\b|\b(update|delete|insert)\(")
writes=defaultdict(set)
for p in (APP/"repositories").glob("*.py"):
    t=ast.parse(p.read_text()); src=p.read_text().splitlines()
    for n in t.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            body="\n".join(src[n.lineno-1:n.end_lineno])
            if WRITE.search(body): writes[module_name(p)].add(n.name)
def owner(rel):
    parts=rel.split("/")
    if parts[0]=="modules": return "modules/"+parts[1]
    return parts[0] if len(parts)>1 else rel
calls=defaultdict(lambda: defaultdict(set))
for p in APP.rglob("*.py"):
    rel=str(p.relative_to(APP))
    if "tests" in rel.split("/") or "__pycache__" in rel or rel.startswith("repositories/"): continue
    t=ast.parse(p.read_text())
    al={}
    for n in ast.walk(t):
        if isinstance(n,ast.ImportFrom) and n.module:
            for a in n.names:
                full=f"{n.module}.{a.name}"
                al[a.asname or a.name]=full
    for n in ast.walk(t):
        if isinstance(n,ast.Call):
            f=n.func
            if isinstance(f,ast.Attribute) and isinstance(f.value,ast.Name):
                m=al.get(f.value.id)
                if m in writes and f.attr in writes[m]:
                    calls[m.split(".")[-1]][owner(rel)].add(f"{f.attr}@{rel}:{n.lineno}")
            elif isinstance(f,ast.Name):
                full=al.get(f.id,"")
                mod,_,fn=full.rpartition(".")
                if mod in writes and fn in writes[mod]:
                    calls[mod.split(".")[-1]][owner(rel)].add(f"{fn}@{rel}:{n.lineno}")
for repo,owners in sorted(calls.items()):
    print(f"== repositories/{repo}.py writes called by {len(owners)} owners")
    for o,s in sorted(owners.items()):
        fns=sorted({x.split('@')[0] for x in s})
        print(f"   {o:28s} {len(s):3d} calls  {', '.join(fns)}")
