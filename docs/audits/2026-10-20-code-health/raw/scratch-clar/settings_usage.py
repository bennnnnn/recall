"""For each Settings field, count reads outside core/settings and core/config (prod and tests)."""
import json, os, re, subprocess
ROOT = "/home/user/recall-audit/apps/api/app"
fields = json.load(open("settings_fields.json"))
prod_src = {}
test_src = {}
for dp, dn, fn in os.walk(ROOT):
    if "__pycache__" in dp: continue
    for f in fn:
        if f.endswith(".py"):
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, ROOT)
            if rel.startswith("core/settings/"):
                continue
            (test_src if "/tests/" in "/" + rel or rel.startswith("tests/") else prod_src)[rel] = open(p).read()
# also scripts, alembic
extra = {}
for base in ["/home/user/recall-audit/apps/api/alembic", "/home/user/recall-audit/scripts"]:
    for dp, dn, fn in os.walk(base):
        for f in fn:
            if f.endswith((".py", ".sh", ".mjs", ".js", ".toml")):
                p = os.path.join(dp, f)
                try: extra[p] = open(p).read()
                except Exception: pass
fly = open("/home/user/recall-audit/fly.toml").read()
rows = []
for name, decls in fields.items():
    pat = re.compile(r"\b" + re.escape(name) + r"\b")
    prod = [r for r, s in prod_src.items() if pat.search(s) and r != "core/config.py"]
    cfg = bool(pat.search(prod_src.get("core/config.py", "")))
    tests = [r for r, s in test_src.items() if pat.search(s)]
    ex = [r for r, s in extra.items() if pat.search(s)]
    env_in_fly = name.upper() in fly
    rows.append((name, decls[0][0], decls[0][2], decls[0][3], len(prod), cfg, len(tests), len(ex), env_in_fly, prod[:4]))
unused = [r for r in rows if r[4] == 0]
print("never read in production code outside settings:", len(unused))
for r in unused:
    print(f"  {r[0]}  ({r[1]}:{r[2]} default={r[3]}) config.py={r[5]} tests={r[6]} scripts={r[7]}")
json.dump(rows, open("settings_usage.json", "w"), indent=1)
