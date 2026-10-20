"""Print the code at the first cited locations of selected findings in an agent report."""
import re, sys
from pathlib import Path
ROOT = Path("/home/user/recall-audit")
report, ids = sys.argv[1], set(sys.argv[2:])
text = Path(report).read_text()
blocks = re.split(r"\n(?=### )", text)
for block in blocks:
    m = re.match(r"### (\S+)", block)
    if not m or m.group(1) not in ids:
        continue
    print("=" * 100); print(block.splitlines()[0][:160])
    locs = re.findall(r"`((?:apps/)[\w/.\-\[\]]+\.(?:py|ts|tsx|json|toml|yml)):(\d+)(?:-(\d+))?", block)
    seen = 0
    for path, a, b in locs:
        if seen >= int(sys.argv[0:1] and 3): break
        p = ROOT / path
        if not p.exists():
            print(f"  !! missing {path}"); continue
        lines = p.read_text(errors="replace").splitlines()
        a = int(a); b = int(b) if b else a
        lo, hi = max(1, a - 1), min(len(lines), max(b, a) + 1, a + 8)
        print(f"  -- {path}:{a}{'-'+str(b) if b != a else ''}")
        for i in range(lo, hi + 1):
            print(f"     {i:5d} {lines[i-1][:150]}")
        seen += 1
