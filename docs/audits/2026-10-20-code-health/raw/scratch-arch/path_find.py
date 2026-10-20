import ast, sys
from collections import deque, defaultdict
from pathlib import Path
APP=Path(sys.argv[1]).resolve(); SRC=sys.argv[2]; DST=sys.argv[3]
def module_name(path):
    parts=path.relative_to(APP.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1]=="__init__" else parts)
def is_tc(t): return (isinstance(t,ast.Name) and t.id=="TYPE_CHECKING") or (isinstance(t,ast.Attribute) and t.attr=="TYPE_CHECKING")
def load_imports(nodes):
    out=[]
    for n in nodes:
        if isinstance(n,(ast.Import,ast.ImportFrom)): out.append(n)
        elif isinstance(n,ast.If) and is_tc(n.test): out.extend(load_imports(n.orelse))
        elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
        elif isinstance(n,(ast.stmt,ast.excepthandler,ast.match_case)): out.extend(load_imports(ast.iter_child_nodes(n)))
    return out
files=[p for p in APP.rglob("*.py") if "tests" not in p.relative_to(APP).parts and "__pycache__" not in p.parts]
names={module_name(p) for p in files}; g=defaultdict(dict)
for p in files:
    name=module_name(p); pkg=name if p.name=="__init__.py" else name.rpartition(".")[0]
    for n in load_imports(ast.parse(p.read_text()).body):
        ts=set()
        if isinstance(n,ast.Import): ts.update(a.name for a in n.names)
        else:
            base=n.module or ""
            if n.level:
                anchor=pkg.rsplit(".",n.level-1)[0]; base=f"{anchor}.{base}" if base else anchor
            ts.add(base); ts.update(f"{base}.{a.name}" for a in n.names)
        for t in (ts&names)-{name}: g[name].setdefault(t, f"{p.relative_to(APP)}:{n.lineno}")
prev={SRC:None}; q=deque([SRC])
while q:
    x=q.popleft()
    if x==DST: break
    for y in g.get(x,{}):
        if y not in prev: prev[y]=x; q.append(y)
if DST not in prev: print("no path"); sys.exit()
path=[DST]
while prev[path[-1]] is not None: path.append(prev[path[-1]])
path.reverse()
for a,b in zip(path,path[1:]): print(f"  {a} -> {b}   ({g[a][b]})")
