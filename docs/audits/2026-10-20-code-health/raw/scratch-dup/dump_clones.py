"""Dump every jscpd clone pair with both excerpts, for manual triage (read-only)."""
import json, sys
ROOT = "/home/user/recall-audit/"
rep = json.load(open("/home/user/recall/tmp/code-audit/raw/jscpd/jscpd-report.json"))
out = []
for i, x in enumerate(rep["duplicates"], 1):
    a, b = x["firstFile"], x["secondFile"]
    out.append(f"===== #{i} [{x['format']}] {x['lines']} lines {x['tokens']} tokens")
    for f in (a, b):
        lines = open(ROOT + f["name"]).read().splitlines()
        s, e = f["start"], f["end"]
        out.append(f"--- {f['name']}:{s}-{e}")
        for n in range(max(1, s), min(len(lines), e) + 1):
            out.append(f"{n:5d}| {lines[n-1]}")
open("/home/user/recall/tmp/code-audit/raw/scratch-dup/clones_dump.txt", "w").write("\n".join(out))
print(len(out))
