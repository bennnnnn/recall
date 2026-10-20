import re, sys
from pathlib import Path
from collections import defaultdict
ROOT=Path(sys.argv[1]).resolve()
IMPORT_RE=re.compile(r"""(?:import|export)\s[^'"]*?from\s*['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\)|require\(\s*['"]([^'"]+)['"]\s*\)""")
def resolve(spec, src):
    if spec.startswith("@/"): base=ROOT/spec[2:]
    elif spec.startswith("."): base=(src.parent/spec).resolve()
    else: return None
    for c in [base, Path(str(base)+".ts"), Path(str(base)+".tsx"), base/"index.ts", base/"index.tsx"]:
        if c.is_file(): return c
    return None
files=[p for d in ["app","components","features","hooks","lib","contexts","ui"] for p in (ROOT/d).rglob("*.ts*") if "__tests__" not in p.parts and ".test." not in p.name]
imp=defaultdict(set)
for f in files:
    for m in IMPORT_RE.finditer(f.read_text(errors="ignore")):
        spec=next(g for g in m.groups() if g); t=resolve(spec,f)
        if t and t!=f: imp[t].add(str(f.relative_to(ROOT)))
targets=sorted([p for p in (ROOT/"components").glob("*.tsx")]+list((ROOT/"hooks").glob("*.ts"))+list((ROOT/"contexts").glob("*.tsx")))
for t in targets:
    print(f"{t.relative_to(ROOT)} <- {sorted(imp.get(t,[]))}")
