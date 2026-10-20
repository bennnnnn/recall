"""Read-only: who imports each shared (non-feature) mobile file?

Shared = top-level components/, hooks/, contexts/, and flat lib/*.ts(x).
For each, list importer "owners": features/<name>, components, hooks, contexts, lib, app, ui.
A file imported (transitively through other shared files is NOT followed) only by one feature is
feature code living outside its feature folder.
Usage: python3 -I mobile_owners.py /home/user/recall-audit/apps/mobile
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
SRC_DIRS = ["app", "components", "features", "hooks", "lib", "contexts", "ui"]
IMPORT_RE = re.compile(
    r"""(?:import|export)\s[^'"]*?from\s*['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\)|require\(\s*['"]([^'"]+)['"]\s*\)|^\s*import\s*['"]([^'"]+)['"]""",
    re.M,
)
EXTS = [".ts", ".tsx", ".js", "/index.ts", "/index.tsx"]


def is_test(p: Path) -> bool:
    s = str(p)
    return "__tests__" in p.parts or ".test." in p.name or "__mocks__" in p.parts


files = [
    p
    for d in SRC_DIRS
    for p in (ROOT / d).rglob("*")
    if p.suffix in (".ts", ".tsx") and "node_modules" not in p.parts and not is_test(p)
]


def resolve(spec: str, src: Path) -> Path | None:
    if spec.startswith("@/"):
        base = ROOT / spec[2:]
    elif spec.startswith("."):
        base = (src.parent / spec).resolve()
    else:
        return None
    if base.is_file():
        return base
    for e in EXTS:
        c = Path(str(base) + e)
        if c.is_file():
            return c
    return None


def owner(p: Path) -> str:
    rel = p.relative_to(ROOT).parts
    if rel[0] == "features":
        return f"features/{rel[1]}"
    return rel[0]


importers: dict[Path, set[str]] = defaultdict(set)
importer_files: dict[Path, set[str]] = defaultdict(set)
for f in files:
    text = f.read_text(errors="ignore")
    for m in IMPORT_RE.finditer(text):
        spec = next(g for g in m.groups() if g)
        tgt = resolve(spec, f)
        if tgt is None or tgt == f:
            continue
        importers[tgt].add(owner(f))
        importer_files[tgt].add(str(f.relative_to(ROOT)))


def shared(p: Path) -> bool:
    rel = p.relative_to(ROOT).parts
    if rel[0] in ("components", "hooks", "contexts"):
        return True
    if rel[0] == "lib" and len(rel) == 2:
        return True
    return False


single = defaultdict(list)
unused = []
for f in sorted(files):
    if not shared(f):
        continue
    owners = importers.get(f, set())
    feats = {o for o in owners if o.startswith("features/")}
    others = owners - feats
    if not owners:
        unused.append(str(f.relative_to(ROOT)))
    elif len(feats) == 1 and not others:
        single[next(iter(feats))].append(str(f.relative_to(ROOT)))

total = 0
for feat, fs in sorted(single.items()):
    total += len(fs)
    print(f"== only {feat} imports ({len(fs)}):")
    for x in fs:
        print(f"   {x}")
print("TOTAL shared files used by exactly one feature and nothing else:", total)
print("shared files with no production importer:", len(unused))
for u in unused:
    print("   ", u)

# --- transitive: walk importers upward through shared files to feature/app roots
rev = defaultdict(set)  # target -> importer files
for f in files:
    text = f.read_text(errors="ignore")
    for m in IMPORT_RE.finditer(text):
        spec = next(g for g in m.groups() if g)
        tgt = resolve(spec, f)
        if tgt is None or tgt == f:
            continue
        rev[tgt].add(f)

from functools import lru_cache
import sys as _s
_s.setrecursionlimit(10000)

def roots(f, seen=None):
    seen = seen or set()
    if f in seen:
        return set()
    seen.add(f)
    out = set()
    for imp in rev.get(f, ()):
        o = owner(imp)
        if shared(imp):
            out |= roots(imp, seen)
            out.add("shared:" + o) if False else None
        else:
            out.add(o)
    return out

trans = defaultdict(list)
for f in sorted(files):
    if not shared(f):
        continue
    r = roots(f)
    feats = {o for o in r if o.startswith("features/")}
    if len(feats) == 1 and not (r - feats):
        trans[next(iter(feats))].append(str(f.relative_to(ROOT)))
print("\n=== TRANSITIVE: shared files reachable only from one feature")
tot = 0
for feat, fs in sorted(trans.items()):
    tot += len(fs)
    print(f"== {feat} ({len(fs)}): " + ", ".join(fs))
print("TOTAL", tot)
