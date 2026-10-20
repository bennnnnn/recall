"""List every `async with <session factory>()` block and the awaited calls inside it.

Read-only: parses source with ast, prints file:line, the awaited call names.
Usage: python3 -I session_awaits.py <app_dir>
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FACTORIES = {"SessionLocal", "session_factory", "async_session", "AsyncSessionLocal"}


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return call_name(node.func)
    if isinstance(node, ast.Attribute):
        base = call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def is_session_ctx(item: ast.withitem) -> bool:
    expr = item.context_expr
    if not isinstance(expr, ast.Call):
        return False
    name = call_name(expr.func)
    return name.split(".")[-1] in FACTORIES


def awaited_calls(body: list[ast.stmt]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Await):
                out.append((node.lineno, call_name(node.value)))
            elif isinstance(node, ast.AsyncFor):
                out.append((node.lineno, "async for " + call_name(node.iter)))
    return out


def main(root: str) -> None:
    base = Path(root)
    for path in sorted(base.rglob("*.py")):
        if "/tests/" in str(path):
            continue
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncWith) and any(is_session_ctx(i) for i in node.items):
                calls = awaited_calls(node.body)
                rel = path.relative_to(base.parent.parent.parent)
                names = ", ".join(f"{n}@{ln}" for ln, n in calls)
                print(f"{rel}:{node.lineno}: {names}")


if __name__ == "__main__":
    main(sys.argv[1])
