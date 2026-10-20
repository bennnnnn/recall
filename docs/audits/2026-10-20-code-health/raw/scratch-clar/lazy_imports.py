"""Count imports of names (not submodules) from packages whose __init__ defines __getattr__ -> Any."""
import ast, os, collections
ROOT = "/home/user/recall-audit/apps/api/app"
lazy = ["chat", "math", "physics", "todos", "notifications", "billing", "memory"]
def submodules(pkg):
    d = os.path.join(ROOT, "modules", pkg)
    return {n[:-3] if n.endswith(".py") else n for n in os.listdir(d)}
def defined_names(pkg):
    tree = ast.parse(open(os.path.join(ROOT, "modules", pkg, "__init__.py")).read())
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name): names.add(t.id)
        elif isinstance(node, ast.ImportFrom):
            for a in node.names: names.add(a.asname or a.name)
        elif isinstance(node, ast.If):  # TYPE_CHECKING blocks
            for sub in ast.walk(node):
                if isinstance(sub, ast.ImportFrom):
                    for a in sub.names: names.add(a.asname or a.name)
    return names
subs = {p: submodules(p) for p in lazy}
defs = {p: defined_names(p) for p in lazy}
counts = collections.Counter(); prod_files = collections.Counter(); names_used = collections.defaultdict(set)
for dp, dn, fn in os.walk(ROOT):
    if "__pycache__" in dp: continue
    for f in fn:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        is_test = "/tests/" in p
        tree = ast.parse(open(p).read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.modules."):
                parts = node.module.split(".")
                if len(parts) == 3 and parts[2] in lazy:
                    pkg = parts[2]
                    for a in node.names:
                        if a.name not in subs[pkg] and a.name not in defs[pkg]:
                            key = ("test" if is_test else "prod", pkg)
                            counts[key] += 1
                            names_used[pkg].add(a.name)
                            if not is_test: prod_files[os.path.relpath(p, ROOT)] += 1
print(sorted(counts.items()))
print("prod files:", len(prod_files), "prod imports:", sum(v for k, v in counts.items() if k[0]=="prod"))
for pkg, ns in names_used.items(): print(pkg, len(ns), sorted(ns)[:12])
