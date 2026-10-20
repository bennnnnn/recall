"""Read-only: collapse the import graph to components and find component cycles.
Components: app.modules.<X>, app.services.<top>, app.core, app.gateways, app.repositories,
app.models, app.background, app.routers, others by top.
Usage: python3 -I component_graph.py APP [load|all]"""
import ast, sys
from collections import defaultdict
from pathlib import Path
sys.setrecursionlimit(100000)
APP=Path(sys.argv[1]).resolve(); MODE=sys.argv[2]
def module_name(path):
    parts=path.relative_to(APP.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1]=="__init__" else parts)
def is_tc(t):
    return (isinstance(t,ast.Name) and t.id=="TYPE_CHECKING") or (isinstance(t,ast.Attribute) and t.attr=="TYPE_CHECKING")
def classify(tree):
    out=[]
    def walk(nodes,kind):
        for n in nodes:
            if isinstance(n,(ast.Import,ast.ImportFrom)): out.append((n,kind))
            elif isinstance(n,ast.If) and is_tc(n.test): walk(n.body,"tc"); walk(n.orelse,kind)
            elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)): walk(ast.iter_child_nodes(n),"deferred")
            else: walk(ast.iter_child_nodes(n),kind)
    walk(tree.body,"load"); return out
def comp(m):
    p=m.split(".")
    if len(p)<2: return m
    if p[1] in ("modules","services") and len(p)>=3: return ".".join(p[:3])
    return ".".join(p[:2])
files=[p for p in APP.rglob("*.py") if "tests" not in p.relative_to(APP).parts and "__pycache__" not in p.parts]
names={module_name(p) for p in files}
edges=defaultdict(lambda: defaultdict(list))
for p in files:
    name=module_name(p); pkg=name if p.name=="__init__.py" else name.rpartition(".")[0]
    for node,kind in classify(ast.parse(p.read_text())):
        if kind=="tc": continue
        if MODE=="load" and kind!="load": continue
        ts=set()
        if isinstance(node,ast.Import): ts.update(a.name for a in node.names)
        else:
            base=node.module or ""
            if node.level:
                anchor=pkg.rsplit(".",node.level-1)[0]; base=f"{anchor}.{base}" if base else anchor
            ts.add(base); ts.update(f"{base}.{a.name}" for a in node.names)
        for t in (ts&names)-{name}:
            a,b=comp(name),comp(t)
            if a!=b: edges[a][b].append(f"{p.relative_to(APP)}:{node.lineno}({kind[0]})")
g={a:set(bs) for a,bs in edges.items()}
index={};low={};st=[];on=set();sccs=[];i=[0]
def sc(v):
    index[v]=low[v]=i[0]; i[0]+=1; st.append(v); on.add(v)
    for w in sorted(g.get(v,())):
        if w not in index: sc(w); low[v]=min(low[v],low[w])
        elif w in on: low[v]=min(low[v],index[w])
    if low[v]==index[v]:
        c=[]
        while True:
            w=st.pop(); on.discard(w); c.append(w)
            if w==v: break
        if len(c)>1: sccs.append(sorted(c))
for v in sorted(set(g)|{x for s in g.values() for x in s}):
    if v not in index: sc(v)
print(f"mode={MODE}: component SCCs:", len(sccs))
for c in sorted(sccs,key=len,reverse=True):
    print(f"--- {len(c)} components:", ", ".join(c))
    cs=set(c)
    for a in c:
        for b in sorted(g.get(a,())):
            if b in cs:
                sites=edges[a][b]
                print(f"    {a} -> {b}  [{len(sites)}] e.g. {', '.join(sites[:3])}")
