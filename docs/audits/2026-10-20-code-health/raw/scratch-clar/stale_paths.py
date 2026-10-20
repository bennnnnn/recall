"""Comments/docstrings in API production code naming a .py/.ts path that exists nowhere (read-only)."""
import io, os, re, tokenize, subprocess
REPO = "/home/user/recall-audit"
ROOT = REPO + "/apps/api/app"
# index of every file path in repo (tracked)
files = subprocess.run(["git", "-C", REPO, "ls-files"], capture_output=True, text=True).stdout.split("\n")
files = [f for f in files if f]
basenames = {}
for f in files:
    basenames.setdefault(os.path.basename(f), []).append(f)
fileset = set(files)
PATH = re.compile(r"(?<![\w.`/-])((?:[\w-]+/)*[\w-]+\.(?:py|tsx?|md|json|toml|sh|mjs))\b")
def exists(ref):
    # accept if any tracked file ends with the ref path
    for f in basenames.get(os.path.basename(ref), []):
        if f.endswith(ref):
            return True
    return False
hits = []
for dp, dn, fn in os.walk(ROOT):
    if "__pycache__" in dp or "/tests" in dp: continue
    for f in fn:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        text = open(p).read()
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except tokenize.TokenError:
            continue
        for tok in toks:
            if tok.type == tokenize.COMMENT or (tok.type == tokenize.STRING and tok.string.lstrip("rbuRBU").startswith(('"""', "'''"))):
                for m in PATH.finditer(tok.string):
                    ref = m.group(1)
                    if not exists(ref):
                        line = tok.start[0] + tok.string[:m.start()].count("\n")
                        hits.append(f"{os.path.relpath(p, REPO)}:{line}\t{ref}\t{tok.string.strip().splitlines()[0][:100] if tok.type==tokenize.COMMENT else ''}")
print(len(hits))
print("\n".join(hits))
