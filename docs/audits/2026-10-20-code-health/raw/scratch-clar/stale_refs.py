"""Comments/docstrings in production code that name a retired module path (read-only)."""
import ast, io, os, re, tokenize, sys
sys.path.insert(0, "/nonexistent")
ROOT = "/home/user/recall-audit/apps/api/app"
src = open(ROOT + "/tests/architecture/boundary_support.py").read()
tree = ast.parse(src)
retired = []
for node in ast.walk(tree):
    if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "RETIRED_LEGACY_MODULES":
        retired = [e.value for e in node.value.elts]
print("retired:", len(retired))
# Build path forms: app.services.chat -> services/chat.py, services.chat, services/chat/
forms = {}
for mod in retired:
    rel = mod[len("app."):]
    slash = rel.replace(".", "/")
    forms[mod] = [re.compile(r"(?<![\w./])(app\.)?" + re.escape(rel) + r"(?![\w])"), re.compile(r"(?<![\w/])" + re.escape(slash) + r"(\.py|/)?(?![\w])")]
hits = []
for dp, dn, fn in os.walk(ROOT):
    if "__pycache__" in dp or "/tests" in dp: continue
    for f in fn:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        text = open(p).read()
        # comments
        chunks = []
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                chunks.append((tok.start[0], tok.string))
            elif tok.type == tokenize.STRING and tok.string.lstrip("rbuRBU").startswith(('"""', "'''")):
                chunks.append((tok.start[0], tok.string))
        for line, s in chunks:
            for mod, pats in forms.items():
                for pat in pats:
                    m = pat.search(s)
                    if m:
                        # skip if file itself exists (module re-created as package etc.)
                        hits.append((os.path.relpath(p, "/home/user/recall-audit"), line, mod, s.strip().replace("\n", " ")[:150]))
                        break
seen = set()
for h in hits:
    key = (h[0], h[1], h[2])
    if key in seen: continue
    seen.add(key)
    print(f"{h[0]}:{h[1]}\t{h[2]}\t{h[3]}")
