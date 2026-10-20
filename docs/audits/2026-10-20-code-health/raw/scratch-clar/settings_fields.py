"""Parse core/settings/*.py and core/config.py for field names and defaults (read-only)."""
import ast, glob, os, re, json
ROOT = "/home/user/recall-audit/apps/api/app"
fields = {}
for path in sorted(glob.glob(ROOT + "/core/settings/*.py")) + [ROOT + "/core/config.py"]:
    tree = ast.parse(open(path).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    name = stmt.target.id
                    if name.startswith("_") or name == "model_config":
                        continue
                    default = ast.unparse(stmt.value) if stmt.value is not None else None
                    fields.setdefault(name, []).append((os.path.relpath(path, ROOT), node.name, stmt.lineno, default))
json.dump(fields, open("settings_fields.json", "w"), indent=1)
dups = {k: v for k, v in fields.items() if len(v) > 1}
print("fields:", len(fields), "declared twice:", dups)
