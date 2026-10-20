"""Numeric literals passed as timeouts/TTLs/limits/retries (read-only AST scan)."""
import ast, os, re, collections
ROOT = "/home/user/recall-audit/apps/api/app"
KW = re.compile(r"^(timeout|.*_timeout|ex|px|ttl|.*_ttl|expire|max_tokens|limit|max_retries|retries|attempts|max_attempts|deadline|.*_seconds|seconds|delay|backoff|interval|count|maxlen|max_len|max_chars|size|batch_size|concurrency|temperature|top_k|k)$")
CALLS = {"sleep", "wait_for", "expire", "setex", "pexpire", "timeout", "Timeout", "set"}
rows = []
def num(n):
    return isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)
for dp, dn, fn in os.walk(ROOT):
    if "__pycache__" in dp or "/tests" in dp: continue
    for f in fn:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, "/home/user/recall-audit")
        tree = ast.parse(open(p).read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call): continue
            fname = node.func.attr if isinstance(node.func, ast.Attribute) else (node.func.id if isinstance(node.func, ast.Name) else "")
            for kw in node.keywords:
                if kw.arg and KW.match(kw.arg) and num(kw.value) and kw.value.value not in (0, 1):
                    rows.append((rel, node.lineno, fname, f"{kw.arg}={kw.value.value}"))
            if fname in ("sleep", "wait_for", "expire", "setex", "pexpire", "Timeout"):
                for a in node.args:
                    if num(a) and a.value not in (0, 1):
                        rows.append((rel, node.lineno, fname, f"arg={a.value}"))
c = collections.Counter(r[3].split("=")[0] for r in rows)
print(len(rows), c.most_common(20))
with open("magic.tsv", "w") as fh:
    for r in rows: fh.write("\t".join(map(str, r)) + "\n")
