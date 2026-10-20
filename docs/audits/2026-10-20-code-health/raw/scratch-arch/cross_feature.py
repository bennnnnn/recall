import re, sys
from pathlib import Path
from collections import defaultdict, Counter
ROOT=Path(sys.argv[1]).resolve()
pairs=Counter(); kinds=Counter(); ex=defaultdict(list)
for f in (ROOT/"features").rglob("*.ts*"):
    if "__tests__" in f.parts or ".test." in f.name: continue
    a=f.relative_to(ROOT).parts[1]
    txt=f.read_text(errors="ignore")
    for m in re.finditer(r"""(?:^|\n)\s*(?:import|export)(\s+type)?\b[^;'"]*?from\s*['"]@/features/([a-z]+)/([^'"]+)['"]""", txt):
        if m.group(1): continue
        b=m.group(2)
        if a==b: continue
        top=m.group(3).split("/")[0]
        pairs[(a,b)]+=1; kinds[top]+=1
        ex[(a,b)].append(f"{f.relative_to(ROOT)} -> features/{b}/{m.group(3)}")
print("cross-feature value imports:", sum(pairs.values()), "by target folder:", dict(kinds))
for (a,b),n in pairs.most_common():
    print(f"  {a:12s} -> {b:12s} {n:3d}  e.g. {ex[(a,b)][0]}")
