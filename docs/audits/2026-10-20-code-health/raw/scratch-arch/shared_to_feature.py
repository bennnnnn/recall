import re, sys
from pathlib import Path
from collections import defaultdict
ROOT=Path(sys.argv[1]).resolve()
IMP=re.compile(r"""^\s*(import|export)\s+(type\s+)?[^;]*?from\s*['"]([^'"]+)['"]""", re.M|re.S)
files=[p for d in ["components","hooks","contexts","lib"] for p in (ROOT/d).rglob("*.ts*") if "__tests__" not in p.parts and ".test." not in p.name and "vendor" not in p.parts]
edges=defaultdict(set)
for f in files:
    txt=f.read_text(errors="ignore")
    for m in re.finditer(r"""(?:^|\n)\s*(?:import|export)(\s+type)?\b[^;'"]*?from\s*['"](@/features/[^'"]+)['"]""", txt):
        if m.group(1): continue
        feat=m.group(2).split("/")[2]
        edges[str(f.relative_to(ROOT))].add((feat, m.group(2)))
n=0
for f,es in sorted(edges.items()):
    if f=="lib/api.ts": continue
    for feat,spec in sorted(es):
        n+=1; print(f"{f} -> {spec}")
print("edges (excluding the lib/api.ts barrel):", n, "files:", len([f for f in edges if f!='lib/api.ts']))
