"""API test functions with no assert, no pytest.raises, and no mock assert_* call:
they pass as long as nothing raises."""
import ast, subprocess, sys
from pathlib import Path
api = Path(sys.argv[1])
files = [f for f in subprocess.run(["git", "ls-files", "app/tests"], cwd=api, capture_output=True, text=True).stdout.split() if f.endswith(".py")]
total = 0
none = []
for rel in files:
    tree = ast.parse((api / rel).read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            total += 1
            has = False
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assert):
                    has = True; break
                if isinstance(sub, ast.Call):
                    f = sub.func
                    name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
                    if name.startswith("assert") or name in ("raises", "fail", "warns", "approx") or name.startswith("check") or name.startswith("_assert") or name.startswith("expect"):
                        has = True; break
                if isinstance(sub, ast.With):
                    for item in sub.items:
                        c = item.context_expr
                        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in ("raises", "warns"):
                            has = True
            if not has:
                none.append(f"{rel}:{node.lineno} {node.name}")
print("test functions:", total, "without any assertion/raises/assert_* call:", len(none))
for n in none[:40]:
    print(" ", n)
