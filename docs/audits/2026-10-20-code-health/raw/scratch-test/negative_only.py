"""Tests whose only checks are negative (assert_not_called/assert_not_awaited, `not in`,
`is None`, `== []`, `is False`). Such a test also passes when the code returns early for
an unrelated reason, so each needs a positive control. Lists them for sampling."""
import ast, subprocess, sys
from pathlib import Path
api = Path(sys.argv[1])
files = [f for f in subprocess.run(["git", "ls-files", "app/tests"], cwd=api, capture_output=True, text=True).stdout.split() if f.endswith(".py")]
out = []
for rel in files:
    tree = ast.parse((api / rel).read_text())
    for fn in ast.walk(tree):
        if not (isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name.startswith("test_")):
            continue
        pos = neg = 0
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr.startswith("assert_"):
                if "not_" in sub.func.attr:
                    neg += 1
                else:
                    pos += 1
            elif isinstance(sub, ast.Assert):
                t = sub.test
                if isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not):
                    neg += 1
                elif isinstance(t, ast.Compare) and (any(isinstance(o, (ast.NotIn, ast.IsNot, ast.NotEq)) for o in t.ops) or any(isinstance(c, ast.Constant) and c.value in (None, False, 0, "") for c in t.comparators) or any(isinstance(c, (ast.List, ast.Dict, ast.Tuple)) and not getattr(c, "elts", getattr(c, "keys", [1])) for c in t.comparators)):
                    neg += 1
                else:
                    pos += 1
            elif isinstance(sub, ast.With):
                for item in sub.items:
                    c = item.context_expr
                    if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr in ("raises",):
                        pos += 1
        if neg and not pos:
            out.append(f"{rel}:{fn.lineno} {fn.name}")
print(len(out), "tests with only negative checks")
for o in out:
    print(" ", o)
