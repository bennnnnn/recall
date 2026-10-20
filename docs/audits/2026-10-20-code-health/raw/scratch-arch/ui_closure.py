import re, sys
from pathlib import Path
ROOT=Path(sys.argv[1]).resolve()
IMPORT_RE=re.compile(r"""(?:import|export)\s[^'"]*?from\s*['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\)|require\(\s*['"]([^'"]+)['"]\s*\)""")
def resolve(spec, src):
    if spec.startswith("@/"): base=ROOT/spec[2:]
    elif spec.startswith("."): base=(src.parent/spec).resolve()
    else: return None
    for c in [base, Path(str(base)+".ts"), Path(str(base)+".tsx"), base/"index.ts", base/"index.tsx"]:
        if c.is_file(): return c
    return None
start=[p for p in (ROOT/"ui").rglob("*.ts*") if "__tests__" not in p.parts]
seen={}; stack=[(p,None) for p in start]
while stack:
    f,par=stack.pop()
    if f in seen: continue
    seen[f]=par
    for m in IMPORT_RE.finditer(f.read_text(errors="ignore")):
        spec=next(g for g in m.groups() if g)
        if spec.startswith("import type"): continue
        t=resolve(spec,f)
        if t and t not in seen: stack.append((t,f))
bad=[f for f in seen if f.relative_to(ROOT).parts[0] in ("features","components","contexts","hooks","app")]
for b in bad:
    chain=[b]
    while seen[chain[-1]] is not None: chain.append(seen[chain[-1]])
    print(" <- ".join(str(c.relative_to(ROOT)) for c in chain))
print("ui closure size", len(seen), "product files reached", len(bad))
libs=sorted(str(f.relative_to(ROOT)) for f in seen if f.relative_to(ROOT).parts[0]=="lib")
print(len(libs), "lib files in ui closure:", ", ".join(libs))
