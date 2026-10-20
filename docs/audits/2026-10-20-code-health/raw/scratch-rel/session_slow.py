"""Find `async with <session>` blocks that await slow external work inside the block."""
import ast, sys, re
from pathlib import Path

ROOT = Path(sys.argv[1])
SLOW = re.compile(
    r"^(complete_structured|complete_text|complete_with_tools|stream_chat_completion|acompletion|aembedding|"
    r"vision_completion|embed_text|embed_many|embed_query|search_web|run_cached_search|_run_search|"
    r"read_bytes|write_bytes|copy_bytes|delete_bytes|delete_prefix|presign_upload|presign_download|"
    r"read_attachment_bytes|verify_uploaded_bytes|to_thread|run_sympy|sleep|wait_for_inflight_stream|"
    r"wait_for_pending_finalize|extract_text_details_async|ocr_scanned_pdf|transcribe\w*|synthesize\w*|"
    r"revoke\w*|send_push\w*|send_email\w*|fetch\w*|generate\w*|lookup\w*|get_subscriber\w*|"
    r"index_attachment|retrieve_for_prompt|post|request|stream)$"
)

def call_name(node):
    f = node.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None

def is_session_cm(item):
    e = item.context_expr
    src = ast.unparse(e)
    return bool(re.search(r"(SessionLocal|session_factory|session_scope|get_session|_session)\(", src)) or src.endswith("begin()")

for p in sorted(ROOT.rglob("*.py")):
    if "/tests/" in str(p):
        continue
    try:
        tree = ast.parse(p.read_text())
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncWith) and any(is_session_cm(i) for i in node.items):
            hits = []
            for sub in node.body:
                for n in ast.walk(sub):
                    if isinstance(n, ast.Await) and isinstance(n.value, ast.Call):
                        name = call_name(n.value)
                        if name and (SLOW.match(name) or "--all" in sys.argv):
                            hits.append(f"{name}@{n.lineno}")
            if hits or "--all" in sys.argv:
                rel = p.relative_to(ROOT.parent.parent.parent)
                print(f"{rel}:{node.lineno}: {', '.join(hits)}")
