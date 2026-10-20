"""Compare .env.example, .env.production.example and fly.toml [env] values with Settings defaults.
Run after settings_fields.py. Read-only."""
import json, re
fields = json.load(open("settings_fields.json"))
def norm(v):
    if v is None: return None
    v = v.strip().strip('"').strip("'")
    if v in ("True", "true"): return "true"
    if v in ("False", "false"): return "false"
    try: return str(float(v.replace("_", "")))
    except ValueError: return v
for env in ["/home/user/recall-audit/apps/api/.env.example", "/home/user/recall-audit/apps/api/.env.production.example", "/home/user/recall-audit/fly.toml"]:
    print("==", env)
    for line in open(env):
        m = re.match(r'^\s*#?\s*([A-Z][A-Z0-9_]+)\s*=\s*"?([^"#\n]*)"?', line)
        if not m: continue
        name, val = m.group(1).lower(), m.group(2).strip()
        if name not in fields or val == "": continue
        default = fields[name][0][3]
        if norm(val) != norm(default):
            print(f"  {name}: env={val!r} code={default}{'  (commented)' if line.lstrip().startswith('#') else ''}")
