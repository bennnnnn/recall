"""Read-only: check every backticked path-like token in a doc against the tree."""
import re, sys
from pathlib import Path
ROOT=Path(sys.argv[1]); DOC=ROOT/sys.argv[2]
API=ROOT/"apps/api/app"; MOB=ROOT/"apps/mobile"
roots=[ROOT, API, API/"modules", API/"services", MOB, MOB/"features", MOB/"lib", API/"modules/chat", ROOT/"docs"]
text=DOC.read_text()
seen=set()
missing=[]
for ln,line in enumerate(text.splitlines(),1):
    for tok in re.findall(r"`([^`\s]+)`", line):
        t=tok.strip().rstrip(",.;:")
        if "/" not in t and not t.endswith((".py",".ts",".tsx",".json",".md",".sh",".mjs")): continue
        if t.startswith(("http","/ws","/","-",".")) and not t.startswith(("./",)): continue
        if any(ch in t for ch in "<>*{}()=|") : continue
        t2=t.removeprefix("./")
        key=(t2)
        if key in seen: continue
        seen.add(key)
        ok=False
        for r in roots:
            p=r/t2
            if p.exists() or Path(str(p)+".py").exists() or Path(str(p)+".ts").exists() or Path(str(p)+".tsx").exists():
                ok=True;break
        if not ok: missing.append((ln,t))
for ln,t in missing: print(f"{sys.argv[2]}:{ln}: `{t}` not found")
print("checked", len(seen), "missing", len(missing))
