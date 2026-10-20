"""Read-only replica of boundary_support._infrastructure_reached for chosen packages."""
import ast, sys
from collections import deque
from pathlib import Path
APP=Path(sys.argv[1]).resolve(); PKGS=sys.argv[2:]
INFRA=("fastapi","httpx","litellm","redis","sqlalchemy","starlette","app.core.db","app.core.redis","app.gateways","app.models.orm","app.repositories")
def module_name(path):
    parts=path.relative_to(APP.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1]=="__init__" else parts)
imports={}
for p in APP.rglob("*.py"):
    if "tests" in p.relative_to(APP).parts or "__pycache__" in p.parts: continue
    name=module_name(p); pkg=name if p.name=="__init__.py" else name.rpartition(".")[0]
    ts=set()
    for n in ast.walk(ast.parse(p.read_text())):
        if isinstance(n,ast.Import): ts.update(a.name for a in n.names)
        elif isinstance(n,ast.ImportFrom):
            base=n.module or ""
            if n.level:
                anchor=pkg.rsplit(".",n.level-1)[0]; base=f"{anchor}.{base}" if base else anchor
            ts.add(base); ts.update(f"{base}.{a.name}" for a in n.names)
    imports[name]=ts
graph={k:(v&imports.keys())-{k} for k,v in imports.items()}
def infra(names): return [r for r in INFRA if any(n==r or n.startswith(r+".") for n in names)]
via={n:None for n in sorted(graph) if any(n==p or n.startswith(p+".") for p in PKGS)}
q=deque(via)
while q:
    n=q.popleft()
    for c in sorted(graph[n]):
        if c not in via and not infra([c]): via[c]=n; q.append(c)
for n in via:
    r=infra(imports[n])
    if r:
        chain=[n]
        while via[chain[-1]] is not None: chain.append(via[chain[-1]])
        print(" -> ".join(reversed(chain)), "imports", ", ".join(r))
