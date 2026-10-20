"""Count mock.patch targets in API tests: string-path patches, patch.object, and
how many hit a private (underscore) name. Also count monkeypatch.setattr on
module globals."""
import ast, collections, sys
from pathlib import Path
tests = Path(sys.argv[1])
string_paths = collections.Counter()
private_string = collections.Counter()
obj_private = collections.Counter()
obj_total = 0
str_total = 0
mp_private = 0
mp_total = 0
private_targets = collections.Counter()
for p in [q for q in tests.rglob("*.py") if "test_zz_audit" not in str(q)]:
    try:
        tree = ast.parse(p.read_text())
    except SyntaxError:
        continue
    rel = str(p)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        fname = None
        if isinstance(f, ast.Name):
            fname = f.id
        elif isinstance(f, ast.Attribute):
            fname = f.attr
            if isinstance(f.value, ast.Name) and f.value.id == "patch" and f.attr == "object":
                fname = "patch.object"
            if isinstance(f.value, ast.Name) and f.value.id == "monkeypatch" and f.attr == "setattr":
                fname = "monkeypatch.setattr"
            if isinstance(f.value, ast.Name) and f.value.id == "patch" and f.attr == "dict":
                fname = "patch.dict"
        if fname == "patch" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            target = node.args[0].value
            str_total += 1
            string_paths[rel] += 1
            last = target.rsplit(".", 1)[-1]
            if last.startswith("_") and not last.startswith("__"):
                private_string[rel] += 1
                private_targets[target] += 1
            # private module in path?
        elif fname == "patch.object" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            obj_total += 1
            name = node.args[1].value
            if isinstance(name, str) and name.startswith("_") and not name.startswith("__"):
                obj_private[rel] += 1
                private_targets[f"<obj>.{name}"] += 1
        elif fname == "monkeypatch.setattr":
            mp_total += 1
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str) and node.args[1].value.startswith("_"):
                mp_private += 1
            elif node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str) and node.args[0].value.rsplit(".",1)[-1].startswith("_"):
                mp_private += 1
print("patch('string.path') calls:", str_total, "of which private leaf:", sum(private_string.values()))
print("patch.object calls:", obj_total, "of which private attr:", sum(obj_private.values()))
print("monkeypatch.setattr calls:", mp_total, "private:", mp_private)
tot_priv = collections.Counter()
for k, v in private_string.items(): tot_priv[k] += v
for k, v in obj_private.items(): tot_priv[k] += v
print("\nfiles with most private-target patches:")
for f, n in tot_priv.most_common(12):
    print(f"  {n:4d} {f}")
print("\nmost-patched private targets:")
for t, n in private_targets.most_common(15):
    print(f"  {n:4d} {t}")
