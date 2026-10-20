"""List select(<Model>...) statements over growing tables that have no .limit( in the same
statement chain (parse only). Heuristic: inspect each Call chain containing select(X)."""
import ast
import sys
from pathlib import Path

GROWING = {"Message", "MessageChunk", "AttachmentChunk", "Attachment", "Memory", "TodoItem",
           "Chat", "ProductEvent", "Suggestion", "UsageDaily"}
root = Path(sys.argv[1])

def chain_methods(node):
    names = []
    cur = node
    while isinstance(cur, ast.Call) and isinstance(cur.func, ast.Attribute):
        names.append(cur.func.attr)
        cur = cur.func.value
    return names, cur

for path in sorted(root.rglob("*.py")):
    if "/tests/" in str(path):
        continue
    tree = ast.parse(path.read_text())
    seen = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        names, base = chain_methods(node)
        if not (isinstance(base, ast.Call) and isinstance(base.func, ast.Name) and base.func.id == "select"):
            continue
        args = [ast.unparse(a) for a in base.args]
        model = next((a.split(".")[0] for a in args if a.split(".")[0] in GROWING), None)
        if not model or "count" in " ".join(args):
            continue
        key = base.lineno
        if key in seen:
            continue
        seen.add(key)
        # only report outermost chains
        if "limit" in names:
            continue
        print(f"{path.relative_to(root.parent)}:{base.lineno}\tselect({', '.join(args)[:60]})\tchain={list(reversed(names))}")
