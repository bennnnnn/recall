"""Mobile exports that no production file imports (resolving import paths), split by whether a
test imports them. Source parsing only (regex over import/export statements).

Usage: python -I tsexports.py /home/user/recall-audit/apps/mobile
Output: file:line  name  kind  in_file_mentions  test_importers  status
"""

from __future__ import annotations

import os
import re
import sys
from collections import defaultdict

ROOT = sys.argv[1]
SRC_DIRS = ("app", "components", "features", "lib", "hooks", "contexts", "ui", "constants", "plugins", "scripts")
EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def is_test(p: str) -> bool:
    return "/__tests__/" in p or re.search(r"\.(test|spec)\.[jt]sx?$", p) is not None or "/__mocks__/" in p


files: list[str] = []
for d in SRC_DIRS:
    base = os.path.join(ROOT, d)
    for dirpath, dirs, fs in os.walk(base):
        dirs[:] = [x for x in dirs if x not in ("node_modules", "vendor")]
        for f in fs:
            if f.endswith(EXTS) and not f.endswith(".d.ts"):
                files.append(os.path.join(dirpath, f))
for f in os.listdir(ROOT):
    if f.endswith(EXTS):
        files.append(os.path.join(ROOT, f))
# jest setup / mocks at root
for extra in ("jest.setup.ts", "jest.setup.js", "__mocks__"):
    p = os.path.join(ROOT, extra)
    if os.path.isdir(p):
        for dirpath, _d, fs in os.walk(p):
            for f in fs:
                if f.endswith(EXTS):
                    files.append(os.path.join(dirpath, f))

src: dict[str, str] = {}
for p in files:
    try:
        src[p] = open(p, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        pass


def resolve(spec: str, frm: str) -> str | None:
    if spec.startswith("@/"):
        base = os.path.join(ROOT, spec[2:])
    elif spec.startswith("."):
        base = os.path.normpath(os.path.join(os.path.dirname(frm), spec))
    else:
        return None
    cands = [base] + [base + e for e in EXTS] + [os.path.join(base, "index" + e) for e in EXTS]
    for c in cands:
        if os.path.isfile(c) and c in src:
            return c
    return None


EXPORT_DECL = re.compile(
    r"^export\s+(?:declare\s+)?(?:default\s+)?(?:async\s+)?(function\*?|const|let|var|class|type|interface|enum|abstract\s+class)\s+([A-Za-z_$][\w$]*)",
    re.M,
)
EXPORT_LIST = re.compile(r"^export\s+(type\s+)?\{([^}]*)\}\s*(?:from\s+[\"']([^\"']+)[\"'])?", re.M)
EXPORT_STAR = re.compile(r"^export\s+\*\s+(?:as\s+(\w+)\s+)?from\s+[\"']([^\"']+)[\"']", re.M)
IMPORT = re.compile(
    r"import\s+(type\s+)?([\w$]+\s*,\s*)?(\{[^}]*\}|\*\s+as\s+[\w$]+|[\w$]+)?\s*(?:,\s*(\{[^}]*\}))?\s*from\s+[\"']([^\"']+)[\"']",
    re.M,
)
SIDE_IMPORT = re.compile(r"import\s+[\"']([^\"']+)[\"']")
REQUIRE = re.compile(r"(?:require|import)\(\s*[\"']([^\"']+)[\"']\s*\)")
JEST_MOCK = re.compile(r"jest\.(?:mock|requireActual|doMock)\(\s*[\"']([^\"']+)[\"']")

exports: dict[str, dict[str, tuple[int, str]]] = defaultdict(dict)  # file -> name -> (line, kind)
reexports: dict[str, list[tuple[str, str, str]]] = defaultdict(list)  # barrel -> (name, target, orig)
star_reexports: dict[str, list[str]] = defaultdict(list)

for p, s in src.items():
    for m in EXPORT_DECL.finditer(s):
        kind, name = m.group(1), m.group(2)
        if s[m.start():m.end()].startswith("export default"):
            exports[p]["default"] = (s.count("\n", 0, m.start()) + 1, "default " + kind)
            continue
        exports[p][name] = (s.count("\n", 0, m.start()) + 1, kind)
    if re.search(r"^export\s+default\s+(?!async\s+function|function|class)", s, re.M):
        exports[p]["default"] = (1, "default")
    for m in EXPORT_LIST.finditer(s):
        names = [x.strip() for x in m.group(2).split(",") if x.strip()]
        target = resolve(m.group(3), p) if m.group(3) else None
        for item in names:
            item = item.replace("type ", "").strip()
            parts = [x.strip() for x in item.split(" as ")]
            orig, alias = parts[0], parts[-1]
            line = s.count("\n", 0, m.start()) + 1
            exports[p][alias] = (line, "re-export" if target else "export-list")
            if target:
                reexports[p].append((alias, target, orig))
    for m in EXPORT_STAR.finditer(s):
        target = resolve(m.group(2), p)
        if target:
            star_reexports[p].append(target)

used_by: dict[tuple[str, str], set[str]] = defaultdict(set)  # (file, name) -> importer files
namespace_users: dict[str, set[str]] = defaultdict(set)


def mark(target: str, name: str, importer: str) -> None:
    used_by[(target, name)].add(importer)


for p, s in src.items():
    for m in IMPORT.finditer(s):
        spec = m.group(5)
        target = resolve(spec, p)
        if not target:
            continue
        default = (m.group(2) or "").strip().rstrip(",").strip()
        clause = m.group(3) or ""
        extra = m.group(4) or ""
        if default:
            mark(target, "default", p)
        if clause.startswith("*"):
            namespace_users[target].add(p)
        elif clause.startswith("{"):
            for item in clause.strip("{}").split(","):
                item = item.replace("type ", "").strip()
                if item:
                    mark(target, item.split(" as ")[0].strip(), p)
        elif clause:
            mark(target, "default", p)
        if extra:
            for item in extra.strip("{}").split(","):
                item = item.replace("type ", "").strip()
                if item:
                    mark(target, item.split(" as ")[0].strip(), p)
    for rx in (SIDE_IMPORT, REQUIRE, JEST_MOCK):
        for m in rx.finditer(s):
            target = resolve(m.group(1), p)
            if target:
                namespace_users[target].add(p)

# Expo Router files and root configs are entry points: what they import or re-export is used.
for p in src:
    rel = os.path.relpath(p, ROOT)
    if rel.startswith("app/") or "/" not in rel:
        for name in list(exports.get(p, {})):
            used_by[(p, name)].add(p + "#entry")
        namespace_users[p].add(p + "#entry")

# propagate through barrels: if barrel X is used, its source is used by the same importers
changed = True
while changed:
    changed = False
    for barrel, items in reexports.items():
        for alias, target, orig in items:
            for imp in list(used_by.get((barrel, alias), ())) + list(namespace_users.get(barrel, ())):
                if imp not in used_by[(target, orig)]:
                    used_by[(target, orig)].add(imp)
                    changed = True
    for barrel, targets in star_reexports.items():
        for target in targets:
            for (f, name), imps in list(used_by.items()):
                if f != barrel:
                    continue
                for imp in list(imps):
                    if name in exports.get(target, {}) and imp not in used_by[(target, name)]:
                        used_by[(target, name)].add(imp)
                        changed = True
            for imp in namespace_users.get(barrel, ()):
                if imp not in namespace_users[target]:
                    namespace_users[target].add(imp)
                    changed = True

rows = []
for p, names in exports.items():
    rel = os.path.relpath(p, ROOT)
    if is_test(p) or rel.startswith(("app/", "scripts/", "plugins/")) or "/" not in rel:
        continue
    for name, (line, kind) in names.items():
        importers = used_by.get((p, name), set()) | namespace_users.get(p, set())
        prod = [i for i in importers if not is_test(i)]
        tests = [i for i in importers if is_test(i)]
        if prod:
            continue
        mentions = len(re.findall(rf"(?<![\w$]){re.escape(name)}(?![\w$])", src[p])) if name != "default" else 0
        status = "TEST-ONLY" if tests else "UNIMPORTED"
        if mentions > 1:
            status += "+in-file"
        rows.append((rel, line, name, kind, mentions, len(tests), status))
rows.sort()
for r in rows:
    print(f"{r[0]}:{r[1]}\t{r[2]}\t{r[3]}\tin_file={r[4]}\ttests={r[5]}\t{r[6]}")
print(f"# files={len(src)} exports={sum(len(v) for v in exports.values())} flagged={len(rows)}", file=sys.stderr)
