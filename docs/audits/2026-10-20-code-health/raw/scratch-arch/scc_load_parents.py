"""Read-only: SCCs of the import graph with deferred imports included (TYPE_CHECKING excluded)."""
import ast, sys
from collections import defaultdict, Counter
from pathlib import Path
sys.setrecursionlimit(100000)
APP = Path(sys.argv[1]).resolve()
exec(open(Path(__file__).with_name('hidden_cycles_lib.py')).read()) if False else None

def module_name(path):
    parts = path.relative_to(APP.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
def is_tc(t):
    return (isinstance(t, ast.Name) and t.id == "TYPE_CHECKING") or (isinstance(t, ast.Attribute) and t.attr == "TYPE_CHECKING")
def classify(tree):
    out=[]
    def walk(nodes, kind):
        for n in nodes:
            if isinstance(n,(ast.Import,ast.ImportFrom)): out.append((n,kind))
            elif isinstance(n, ast.If) and is_tc(n.test):
                walk(n.body,"tc"); walk(n.orelse,kind)
            elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.Lambda)):
                walk(ast.iter_child_nodes(n),"deferred")
            else: walk(ast.iter_child_nodes(n),kind)
    walk(tree.body,"load"); return out
files=[p for p in APP.rglob("*.py") if "tests" not in p.relative_to(APP).parts and "__pycache__" not in p.parts]
names={module_name(p) for p in files}
g=defaultdict(set)
for p in files:
    name=module_name(p); pkg=name if p.name=="__init__.py" else name.rpartition(".")[0]
    for node,kind in classify(ast.parse(p.read_text())):
        if kind!="load": continue
        ts=set()
        if isinstance(node,ast.Import): ts.update(a.name for a in node.names)
        else:
            base=node.module or ""
            if node.level:
                anchor=pkg.rsplit(".",node.level-1)[0]; base=f"{anchor}.{base}" if base else anchor
            ts.add(base); ts.update(f"{base}.{a.name}" for a in node.names)
        for t in (ts & names)-{name}:
            g[name].add(t)
            parts=t.split(".")
            for i in range(2,len(parts)):
                par=".".join(parts[:i])
                if par in names and par!=name: g[name].add(par)
# tarjan
index={};low={};st=[];on=set();sccs=[];i=[0]
def sc(v):
    index[v]=low[v]=i[0]; i[0]+=1; st.append(v); on.add(v)
    for w in g.get(v,()):
        if w not in index: sc(w); low[v]=min(low[v],low[w])
        elif w in on: low[v]=min(low[v],index[w])
    if low[v]==index[v]:
        comp=[]
        while True:
            w=st.pop(); on.discard(w); comp.append(w)
            if w==v: break
        if len(comp)>1: sccs.append(sorted(comp))
for v in sorted(names):
    if v not in index: sc(v)
sccs.sort(key=len, reverse=True)
print("SCCs (deferred included):", [len(c) for c in sccs][:20])
for c in sccs[:3]:
    tops=Counter(".".join(m.split(".")[:3]) for m in c)
    print("--- SCC size", len(c)); 
    for t,n in tops.most_common(): print(f"   {n:4d} {t}")
