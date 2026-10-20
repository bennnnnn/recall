"""List Redis-style .set(key, value, ...) calls and whether they carry an expiry (parse only)."""
import ast
import sys
from pathlib import Path

root = Path(sys.argv[1])
for path in sorted(root.rglob("*.py")):
    if "/tests/" in str(path):
        continue
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in {"set", "setnx", "mset", "hset", "sadd", "zadd", "rpush", "lpush"}:
            continue
        if node.func.attr == "set" and len(node.args) < 2:
            continue
        kws = {k.arg for k in node.keywords if k.arg}
        has_ttl = bool(kws & {"ex", "px", "keepttl", "exat", "pxat"})
        recv = ast.unparse(node.func.value)
        print(f"{path.relative_to(root.parent.parent)}:{node.lineno}\t{recv}.{node.func.attr}\tttl={has_ttl}\tkw={sorted(kws)}")
