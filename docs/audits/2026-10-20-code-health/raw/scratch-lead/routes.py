"""List every FastAPI route in apps/api/app with its auth dependency (static read)."""
import ast, sys
from pathlib import Path
ROOT = Path("/home/user/recall-audit/apps/api/app")
AUTH_NAMES = {"get_current_user", "current_user", "CurrentUser", "require_user", "get_current_user_id", "AuthUser", "require_admin", "admin_user", "get_admin_user", "verify_admin"}
rows = []
for path in list(ROOT.glob("modules/*/api*.py")) + list(ROOT.glob("modules/*/*_api.py")) + list(ROOT.glob("routers/*.py")):
    tree = ast.parse(path.read_text())
    router_deps = ""
    src = path.read_text()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in {"get","post","put","patch","delete","websocket","api_route"}:
                    route = dec.args[0].value if dec.args and isinstance(dec.args[0], ast.Constant) else "?"
                    seg = ast.get_source_segment(src, node.args) or ""
                    deps = ast.get_source_segment(src, dec) or ""
                    auth = [n for n in AUTH_NAMES if n in seg or n in deps]
                    rows.append((str(path.relative_to(ROOT)), dec.func.attr.upper(), route, node.name, ",".join(sorted(auth)) or "-"))
for r in sorted(rows):
    print("\t".join(r))
