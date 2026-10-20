"""Attributes tests set on unspecced MagicMock/SimpleNamespace "users" that the User
ORM model does not have. An attribute the model lacks is one the code never reads,
so the test thinks it configured a branch it did not."""
import ast, collections, sys
from pathlib import Path
api = Path(sys.argv[1])
# Real attributes: class-level names in app/models/orm/user.py User class (+ properties/methods).
src = (api / "app/models/orm/user.py").read_text()
tree = ast.parse(src)
real = set()
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == "User":
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                real.add(item.target.id)
            elif isinstance(item, ast.Assign):
                for t in item.targets:
                    if isinstance(t, ast.Name):
                        real.add(t.id)
            elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                real.add(item.name)
real |= {"id", "metadata", "registry", "__dict__", "_sa_instance_state"}
unknown = collections.defaultdict(list)
for p in (api / "app/tests").rglob("*.py"):
    t = ast.parse(p.read_text())
    for fn in ast.walk(t):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            continue
        mock_users = set()
        for node in ast.walk(fn):
            # user = MagicMock() / Mock() / AsyncMock()
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if (name == "user" or name.endswith("_user") or name == "u") and isinstance(node.value, ast.Call):
                    f = node.value.func
                    fname = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
                    if fname in ("MagicMock", "Mock", "AsyncMock", "NonCallableMagicMock") and not any(k.arg in ("spec", "spec_set") for k in node.value.keywords) and not node.value.args:
                        mock_users.add(name)
        if not mock_users:
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name) and tgt.value.id in mock_users:
                        if tgt.attr not in real and not tgt.attr.startswith("__"):
                            unknown[tgt.attr].append(f"{p.relative_to(api)}:{node.lineno}")
print("User model attributes:", len(real))
print("attributes set on unspecced mock users that User does not have:", sum(len(v) for v in unknown.values()))
for attr, locs in sorted(unknown.items(), key=lambda kv: -len(kv[1])):
    print(f"  {attr}: {len(locs)}  e.g. {locs[:3]}")
