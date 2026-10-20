"""Read-only: which function-local (deferred) imports hide an import cycle?

Builds the load-time graph (same rules as tests/architecture/boundary_support) and the
deferred edges. A deferred edge A -> B "hides a cycle" when B already reaches A through
load-time imports, i.e. moving the import to module level would create a cycle.
Usage: python3 -I hidden_cycles.py /home/user/recall-audit/apps/api/app
"""

from __future__ import annotations

import ast
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

APP = Path(sys.argv[1]).resolve()


def module_name(path: Path) -> str:
    parts = path.relative_to(APP.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def is_tc(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def classify(tree: ast.Module):
    """Yield (node, kind) for every import: kind in load / deferred / type_checking."""
    out = []

    def walk(nodes, kind):
        for node in nodes:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                out.append((node, kind))
            elif isinstance(node, ast.If) and is_tc(node.test):
                walk(node.body, "type_checking" if kind == "load" else kind)
                walk(node.orelse, kind)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                walk(ast.iter_child_nodes(node), "deferred")
            else:
                walk(ast.iter_child_nodes(node), kind)

    walk(tree.body, "load")
    return out


files = [
    p
    for p in APP.rglob("*.py")
    if "tests" not in p.relative_to(APP).parts and "__pycache__" not in p.parts
]
names = {module_name(p) for p in files}
load = defaultdict(set)
deferred = defaultdict(set)  # (src) -> {(target, lineno)}
deferred_sites = []
for p in files:
    name = module_name(p)
    pkg = name if p.name == "__init__.py" else name.rpartition(".")[0]
    tree = ast.parse(p.read_text())
    for node, kind in classify(tree):
        targets = set()
        if isinstance(node, ast.Import):
            targets.update(a.name for a in node.names)
        else:
            base = node.module or ""
            if node.level:
                anchor = pkg.rsplit(".", node.level - 1)[0]
                base = f"{anchor}.{base}" if base else anchor
            targets.add(base)
            targets.update(f"{base}.{a.name}" for a in node.names)
        targets = (targets & names) - {name}
        if kind == "load":
            load[name] |= targets
        elif kind == "deferred":
            for t in targets:
                deferred_sites.append((name, t, node.lineno, str(p.relative_to(APP))))

# also: importing a.b.c loads a and a.b (package inits)
def with_parents(g):
    g2 = defaultdict(set)
    for k, vs in g.items():
        for v in vs:
            g2[k].add(v)
            parts = v.split(".")
            for i in range(2, len(parts)):
                parent = ".".join(parts[:i])
                if parent in names and parent != k:
                    g2[k].add(parent)
    return g2

loadg = with_parents(load)


def reaches(src, dst):
    seen = {src}
    q = deque([src])
    while q:
        n = q.popleft()
        if n == dst:
            return True
        for c in loadg.get(n, ()):
            if c not in seen:
                seen.add(c)
                q.append(c)
    return False


print(f"deferred app-internal import sites: {len(deferred_sites)}")
by_layer = Counter(s[3].split('/')[0] if '/' in s[3] else s[3] for s in deferred_sites)
print("by source top dir:", dict(by_layer.most_common()))
hiding = []
for src, dst, line, rel in deferred_sites:
    if reaches(dst, src):
        hiding.append((rel, line, src, dst))
print(f"deferred sites that hide a load-time cycle (dst reaches src at load time): {len(hiding)}")
c = Counter(h[0] for h in hiding)
for f, n in c.most_common(60):
    print(f"  {n:3d} {f}")
print("== sample sites")
for h in sorted(hiding)[:400]:
    print(f"  {h[0]}:{h[1]} {h[2]} -> {h[3]}")
