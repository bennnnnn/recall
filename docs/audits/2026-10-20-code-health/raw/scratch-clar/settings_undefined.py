import json, os, re, ast
ROOT = "/home/user/recall-audit/apps/api/app"
fields = set(json.load(open("settings_fields.json")))
# methods/properties on Settings
cfg = ast.parse(open(ROOT + "/core/config.py").read())
members = set()
for node in ast.walk(cfg):
    if isinstance(node, ast.ClassDef) and node.name == "Settings":
        for st in node.body:
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                members.add(st.name)
known = fields | members | {"model_dump", "model_copy", "model_fields", "model_config", "model_validate", "model_fields_set"}
pat = re.compile(r"\b(?:settings|_settings|get_settings\(\)|self\.settings|ctx\.settings|deps\.settings|state\.settings|turn\.settings)\.([a-zA-Z_]\w*)")
missing = {}
for dp, dn, fn in os.walk(ROOT):
    if "__pycache__" in dp or "/tests" in dp: continue
    for f in fn:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        for i, line in enumerate(open(p), 1):
            for m in pat.finditer(line):
                a = m.group(1)
                if a not in known:
                    missing.setdefault(a, []).append(f"{os.path.relpath(p, ROOT)}:{i}")
for a, locs in sorted(missing.items()):
    print(a, len(locs), locs[:3])
print("members:", sorted(members))
