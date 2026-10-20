"""Awaited DB/Redis/session calls inside for-loops (parse only). Prints file:line and call."""
import ast, sys, pathlib

ROOT = pathlib.Path(sys.argv[1])
DB_HINTS = ("session.", "_repo.", "repo.", "repository.", "SessionLocal", "redis.", "crud.",
            "session_factory", ".execute", ".scalar", ".get_by_id", ".commit", ".flush", ".refresh",
            "service.", "enqueue", "counters.")

def call_name(node):
    f = node.func
    parts = []
    while isinstance(f, ast.Attribute):
        parts.append(f.attr)
        f = f.value
    if isinstance(f, ast.Name):
        parts.append(f.id)
    return ".".join(reversed(parts))

class V(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.loop_depth = 0
    def visit_For(self, node):
        self.loop_depth += 1
        self.generic_visit(node)
        self.loop_depth -= 1
    visit_AsyncFor = visit_For
    visit_While = visit_For
    def visit_Await(self, node):
        if self.loop_depth and isinstance(node.value, ast.Call):
            name = call_name(node.value)
            if any(h in name or name.startswith(h.rstrip(".")) for h in DB_HINTS):
                print(f"{self.path}:{node.lineno}: {name}")
        self.generic_visit(node)
    def visit_AsyncWith(self, node):
        if self.loop_depth:
            for item in node.items:
                if isinstance(item.context_expr, ast.Call) and "Session" in call_name(item.context_expr):
                    print(f"{self.path}:{node.lineno}: async with {call_name(item.context_expr)} (in loop)")
        self.generic_visit(node)

for path in sorted(ROOT.rglob("*.py")):
    s = str(path)
    if "/tests/" in s:
        continue
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        continue
    V(path.relative_to(ROOT.parent.parent.parent)).visit(tree)
