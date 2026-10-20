"""List awaited calls made inside `async with SessionLocal()` style blocks (parse only)."""
import ast, sys, pathlib

ROOT = pathlib.Path(sys.argv[1])
NETWORK_HINTS = ("complete", "embed", "acompletion", "aembedding", "write_bytes", "read_bytes",
                 "copy_bytes", "delete_bytes", "presign", "search", "fetch", "send", "post", "get_or_embed",
                 "generate", "summarize", "vision", "transcribe", "tavily", "pubchem", "push", "email",
                 "resolve_reference", "classify", "enqueue", "revenuecat", "apple", "google", "http")

def is_session_ctx(expr):
    if isinstance(expr, ast.Call):
        f = expr.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        return name in ("SessionLocal", "session_factory", "_session_factory")
    return False

def call_name(node):
    f = node.func
    parts = []
    while isinstance(f, ast.Attribute):
        parts.append(f.attr)
        f = f.value
    if isinstance(f, ast.Name):
        parts.append(f.id)
    return ".".join(reversed(parts))

for path in sorted(ROOT.rglob("*.py")):
    if "/tests/" in str(path):
        continue
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncWith) and any(is_session_ctx(i.context_expr) for i in node.items):
            awaited = []
            for sub in ast.walk(node):
                if isinstance(sub, ast.Await) and isinstance(sub.value, ast.Call):
                    awaited.append(call_name(sub.value))
            hits = [a for a in awaited if any(h in a.lower() for h in NETWORK_HINTS)]
            if hits:
                print(f"{path.relative_to(ROOT.parent.parent)}:{node.lineno}: {sorted(set(hits))}")
