"""List module-level mutable state in apps/api/app (excluding tests)."""
import ast
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
MUTABLE_CALLS = {
    "dict", "set", "list", "deque", "defaultdict", "OrderedDict", "Counter",
    "Lock", "Semaphore", "BoundedSemaphore", "Event", "Condition", "Queue",
    "TtlCache", "WeakValueDictionary", "WeakKeyDictionary", "WeakSet", "ContextVar",
    "LRUCache", "TTLCache",
}
out = []
for p in sorted(ROOT.rglob("*.py")):
    if "/tests/" in str(p):
        continue
    try:
        tree = ast.parse(p.read_text())
    except Exception as e:
        print("PARSE FAIL", p, e)
        continue
    for node in tree.body:
        targets = []
        value = None
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        names = []
        for t in targets:
            if isinstance(t, ast.Name):
                names.append(t.id)
        if not names:
            continue
        kind = None
        if isinstance(value, (ast.Dict, ast.Set, ast.List)):
            # literal: only flag if empty (likely runtime-mutated registry) 
            if isinstance(value, ast.Dict) and not value.keys:
                kind = "empty-dict-literal"
            elif isinstance(value, ast.List) and not value.elts:
                kind = "empty-list-literal"
            elif isinstance(value, ast.Set) and not value.elts:
                kind = "empty-set-literal"
        elif isinstance(value, ast.Call):
            f = value.func
            fname = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
            if fname in MUTABLE_CALLS:
                kind = f"call:{fname}"
        if kind:
            out.append(f"{p.relative_to(ROOT.parent.parent.parent)}:{node.lineno}: {','.join(names)} = {kind}")
    # also functions decorated with lru_cache / cache
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.decorator_list:
                dn = None
                if isinstance(d, ast.Call):
                    d2 = d.func
                else:
                    d2 = d
                if isinstance(d2, ast.Attribute):
                    dn = d2.attr
                elif isinstance(d2, ast.Name):
                    dn = d2.id
                if dn in {"lru_cache", "cache", "cached", "alru_cache"}:
                    out.append(f"{p.relative_to(ROOT.parent.parent.parent)}:{node.lineno}: @{dn} {node.name} async={isinstance(node, ast.AsyncFunctionDef)}")
    # global statements inside functions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Global):
                    out.append(f"{p.relative_to(ROOT.parent.parent.parent)}:{sub.lineno}: global {','.join(sub.names)} in {node.name}")
print("\n".join(out))
