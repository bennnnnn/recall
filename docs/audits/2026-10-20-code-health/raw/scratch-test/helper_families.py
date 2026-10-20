"""Find helper/fixture families defined in many API test modules.

Groups module-level function/class definitions in app/tests by a normalized name
(lowercased, leading underscores stripped) and by family regexes; prints how many
modules define each family.
"""
import ast, collections, re, sys
from pathlib import Path
tests = Path(sys.argv[1])
defs = collections.defaultdict(list)
for p in [q for q in tests.rglob("*.py") if "test_zz_audit" not in str(q)]:
    try:
        tree = ast.parse(p.read_text())
    except SyntaxError:
        continue
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name.startswith("test_") or node.name.startswith("Test"):
                continue
            defs[node.name.lstrip("_").lower()].append(f"{p.relative_to(tests.parent.parent)}:{node.lineno}")
families = {
    "fake session / session context manager": r"(fake)?session(cm|local|_cm|_factory|_local|ctx|_ctx)?$|^session_?(cm|factory)$|^fakesession|sessioncm|session_local_side_effect|^db$|^session$",
    "fake/make user": r"^(make_|fake_|stub_|build_)?user(_row|_obj|_mock)?$|^(free|pro|plus)_user$",
    "fake chat": r"^(make_|fake_|stub_)?chat(_row|_obj)?$",
    "settings builder": r"^(make_|build_|test_|fake_)?settings$|_settings$",
    "fake llm / stream / completion": r"(fake|mock|stub).*(llm|stream|completion|acompletion|tokens?)|^(llm|stream|completion)_?(fake|mock|stub)",
    "fake redis": r"(fake|mock|stub).*redis|redis_(fake|mock|stub)",
    "fake message rows": r"^(make_|fake_|stub_)?(msg|message|messages|row|rows)$",
}
for fam, rx in families.items():
    hits = {k: v for k, v in defs.items() if re.search(rx, k)}
    modules = {loc.split(":")[0] for v in hits.values() for loc in v}
    print(f"{fam}: {sum(len(v) for v in hits.values())} definitions in {len(modules)} modules; names: {sorted(hits)[:12]}")
print()
print("Same helper name defined in >= 8 modules:")
for name, locs in sorted(defs.items(), key=lambda kv: -len({l.split(':')[0] for l in kv[1]})):
    mods = {l.split(":")[0] for l in locs}
    if len(mods) >= 8:
        print(f"  {len(mods):3d} modules  {name}")
