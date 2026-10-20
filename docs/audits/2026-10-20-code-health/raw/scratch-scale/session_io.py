"""Heuristic: awaited calls inside `async with SessionLocal()/session_factory()` blocks
whose dotted name hints at provider / network IO (parse only, no imports)."""
import ast
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
HINT = re.compile(
    r"(llm|litellm|embed|complete|summar|generate|revise|merge_memory|extract_todo|"
    r"httpx|fetch|send_|dispatch|expo|revenuecat|storage|delete_storage|delete_prefix|"
    r"upload|download|ocr|transcribe|tavily|search_web|apple|google|resend|email)",
    re.I,
)

def is_session_cm(item: ast.withitem) -> bool:
    src = ast.unparse(item.context_expr)
    return "SessionLocal(" in src or "session_factory(" in src

for path in sorted(root.rglob("*.py")):
    if "/tests/" in str(path):
        continue
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncWith) and any(is_session_cm(i) for i in node.items):
            for sub in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(sub, ast.Await) and isinstance(sub.value, ast.Call):
                    name = ast.unparse(sub.value.func)
                    if HINT.search(name) and "repo" not in name.lower():
                        print(f"{path.relative_to(root.parent)}:{sub.lineno}\t{name}")
