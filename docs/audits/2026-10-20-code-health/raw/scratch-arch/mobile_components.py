import re, sys
from pathlib import Path
from collections import defaultdict
sys.setrecursionlimit(10000)
ROOT=Path(sys.argv[1]).resolve()
RX=re.compile(r"""(?:^|\n)\s*(?:import|export)(\s+type)?\b[^;'"]*?from\s*['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\)""")
def resolve(spec, src):
    if spec.startswith("@/"): base=ROOT/spec[2:]
    elif spec.startswith("."): base=(src.parent/spec).resolve()
    else: return None
    for c in [base, Path(str(base)+".ts"), Path(str(base)+".tsx"), base/"index.ts", base/"index.tsx"]:
        if c.is_file(): return c
    return None
def comp(p):
    r=p.relative_to(ROOT).parts
    return f"features/{r[1]}" if r[0]=="features" else r[0]
files=[p for d in ["app","components","features","hooks","lib","contexts","ui"] for p in (ROOT/d).rglob("*.ts*") if "__tests__" not in p.parts and ".test." not in p.name and "vendor" not in p.parts and not p.name.endswith(".d.ts")]
g=defaultdict(set); ex={}
for f in files:
    for m in RX.finditer(f.read_text(errors="ignore")):
        if m.group(1): continue
        spec=m.group(2) or m.group(3); t=resolve(spec,f)
        if not t: continue
        a,b=comp(f),comp(t)
        if a!=b and not (a=="lib" and f.name=="api.ts" and f.parent.name=="lib"):
            g[a].add(b); ex.setdefault((a,b), f"{f.relative_to(ROOT)} -> {t.relative_to(ROOT)}")
index={};low={};st=[];on=set();sccs=[];i=[0]
def sc(v):
    index[v]=low[v]=i[0];i[0]+=1;st.append(v);on.add(v)
    for w in sorted(g.get(v,())):
        if w not in index: sc(w); low[v]=min(low[v],low[w])
        elif w in on: low[v]=min(low[v],index[w])
    if low[v]==index[v]:
        c=[]
        while True:
            w=st.pop();on.discard(w);c.append(w)
            if w==v:break
        if len(c)>1: sccs.append(sorted(c))
for v in sorted(set(g)|{x for s in g.values() for x in s}):
    if v not in index: sc(v)
for c in sccs: print(len(c), c)
