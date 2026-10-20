"""Classify sleep calls in API tests: in the test body vs in a nested fake.

Prints, per file, the count and total seconds of literal sleeps that run in the
test function body itself (coordination waits), and those inside nested defs
(fakes; usually 'hang until cancelled' or 'take a while').
"""
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for path in sorted(root.rglob("*.py")):
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError:
        continue

    def visit(node, stack):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, stack + [child])
            elif isinstance(child, ast.ClassDef):
                visit(child, stack + [child])
            else:
                if isinstance(child, ast.Call):
                    f = child.func
                    name = None
                    if isinstance(f, ast.Attribute) and f.attr == "sleep":
                        if isinstance(f.value, ast.Name):
                            name = f"{f.value.id}.sleep"
                    elif isinstance(f, ast.Name) and f.id == "sleep":
                        name = "sleep"
                    if name and child.args:
                        arg = child.args[0]
                        val = None
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)):
                            val = float(arg.value)
                        funcs = [s for s in stack if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))]
                        top = funcs[0].name if funcs else "<module>"
                        nested = len(funcs) > 1 or (funcs and not funcs[0].name.startswith("test_"))
                        rows.append((str(path.relative_to(root.parent.parent)), child.lineno, name, val, top, "fake/helper" if nested else "test-body"))
                visit(child, stack)

    visit(tree, [])

import collections
by_kind = collections.Counter(r[5] for r in rows)
print("total sleep calls:", len(rows), dict(by_kind))
zero = [r for r in rows if r[3] == 0.0]
print("sleep(0) yields:", len(zero))
body = [r for r in rows if r[5] == "test-body" and (r[3] is None or r[3] > 0)]
print("\nNon-zero sleeps directly in test bodies (coordination waits):", len(body))
for r in body:
    print(f"  {r[0]}:{r[1]} {r[2]}({r[3]}) in {r[4]}")
per_file = collections.defaultdict(float)
for r in rows:
    if r[5] == "test-body" and r[3]:
        per_file[r[0]] += r[3]
print("\nTotal literal seconds slept in test bodies per file:")
for f, s in sorted(per_file.items(), key=lambda kv: -kv[1])[:15]:
    print(f"  {s:6.2f}s {f}")
