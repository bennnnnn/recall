"""Functions that take a `session` argument and await network-like calls (parse only)."""
import ast, sys, pathlib

ROOT = pathlib.Path(sys.argv[1])
HINTS = ("complete_structured", "complete_text", "complete_with_tools", "acompletion", "aembedding",
         "embed_text", "embed_many", "get_or_embed_query", "write_bytes", "read_bytes", "copy_bytes",
         "delete_bytes", "delete_prefix", "presign", "search_images", "search_web", "fetch_safely",
         "summarize", "vision_completion", "transcribe", "send_push", "send_email", "resolve_reference",
         "_ask_", "generate_image", "pubchem", "httpx", "client.post", "client.get", "revenuecat",
         "storage_keys", "llm.", "_llm", "extract_with", "classify_")

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
        if isinstance(node, ast.AsyncFunctionDef):
            argnames = [a.arg for a in node.args.args + node.args.kwonlyargs]
            if "session" not in argnames:
                continue
            awaited = []
            for sub in ast.walk(node):
                if isinstance(sub, ast.Await) and isinstance(sub.value, ast.Call):
                    awaited.append(call_name(sub.value))
            hits = sorted({a for a in awaited if any(h in a for h in HINTS)})
            if hits:
                print(f"{path.relative_to(ROOT.parent.parent)}:{node.lineno} {node.name}: {hits}")
