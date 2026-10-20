"""Imports of underscore-prefixed names from another module (production code only)."""
import ast, os, collections
ROOT = "/home/user/recall-audit/apps/api/app"
rows = []
by_src = collections.Counter(); by_name = collections.Counter()
for dp, dn, fn in os.walk(ROOT):
    if "__pycache__" in dp or "/tests" in dp: continue
    for f in fn:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        tree = ast.parse(open(p).read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    if a.name.startswith("_") and not a.name.startswith("__"):
                        rel = os.path.relpath(p, ROOT)
                        rows.append((rel, node.lineno, node.module, a.name))
                        by_src[node.module] += 1
                        by_name[(node.module, a.name)] += 1
print("private-name imports:", len(rows), "importing files:", len({r[0] for r in rows}), "source modules:", len(by_src))
for m, c in by_src.most_common(12): print(f"  {c:3d}  {m}")
print("most-imported private names:")
for (m, n), c in by_name.most_common(10): print(f"  {c:3d}  {m}.{n}")

def domain(mod_or_path):
    parts = mod_or_path.replace("/", ".").replace(".py", "").split(".")
    if parts[0] == "app": parts = parts[1:]
    if parts[0] == "modules" and len(parts) > 1: return "modules." + parts[1]
    if parts[0] == "services" and len(parts) > 1 and parts[1] in ("law_binding", "quota", "mcp"): return "services." + parts[1]
    return parts[0]
cross = [r for r in rows if domain(r[0]) != domain(r[2])]
print("cross-domain private imports:", len(cross))
cc = collections.Counter((domain(r[0]), r[2], r[3]) for r in cross)
for (src, m, n), c in cc.most_common(25): print(f"  {c:2d}  {src} <- {m}.{n}")
