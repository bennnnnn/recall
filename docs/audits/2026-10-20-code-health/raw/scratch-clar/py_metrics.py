"""Read-only AST metrics for apps/api/app (production code, tests excluded).

Usage: python3 -I py_metrics.py <root> <outdir>
Writes TSV files to outdir: functions.tsv (qualname, file, line, length, depth),
excepts.tsv (broad except handlers and what their body does), typing.txt.
"""

from __future__ import annotations

import ast
import io
import os
import re
import sys
import tokenize

ROOT = sys.argv[1]
OUT = sys.argv[2]

CONTROL = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
)
try:
    CONTROL = CONTROL + (ast.TryStar,)  # type: ignore[attr-defined]
except AttributeError:
    pass

FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)


def iter_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        parts = dirpath.split(os.sep)
        if "tests" in parts or "__pycache__" in parts:
            continue
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def max_depth(node: ast.AST, depth: int = 0) -> int:
    """Deepest control-flow nesting inside node, not descending into nested defs."""
    best = depth
    for child in ast.iter_child_nodes(node):
        if isinstance(child, FUNCS + (ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(child, CONTROL):
            # elif chains: an If in orelse of an If is the same level
            best = max(best, _depth_control(child, depth + 1))
        else:
            best = max(best, max_depth(child, depth))
    return best


def _depth_control(node: ast.AST, depth: int) -> int:
    best = depth
    if isinstance(node, ast.If):
        for child in node.body:
            best = max(best, _walk_stmt(child, depth))
        # treat `elif` as same level
        orelse = node.orelse
        if len(orelse) == 1 and isinstance(orelse[0], ast.If):
            best = max(best, _depth_control(orelse[0], depth))
        else:
            for child in orelse:
                best = max(best, _walk_stmt(child, depth))
        best = max(best, max_depth(node.test, depth))
        return best
    for child in ast.iter_child_nodes(node):
        best = max(best, _walk_stmt(child, depth))
    return best


def _walk_stmt(node: ast.AST, depth: int) -> int:
    if isinstance(node, FUNCS + (ast.ClassDef, ast.Lambda)):
        return depth
    if isinstance(node, CONTROL):
        return _depth_control(node, depth + 1)
    if isinstance(node, ast.ExceptHandler) or isinstance(node, ast.match_case):
        best = depth
        for child in ast.iter_child_nodes(node):
            best = max(best, _walk_stmt(child, depth))
        return best
    return max_depth(node, depth)


class Collector(ast.NodeVisitor):
    def __init__(self, path: str, lines: list[str]):
        self.path = path
        self.lines = lines
        self.stack: list[str] = []
        self.funcs: list[tuple[str, str, int, int, int]] = []
        self.excepts: list[tuple[str, int, str, str, str]] = []

    def _visit_scope(self, node, name):
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_ClassDef(self, node):
        self._visit_scope(node, node.name)

    def _func(self, node):
        qual = ".".join(self.stack + [node.name])
        length = (node.end_lineno or node.lineno) - node.lineno + 1
        depth = 0
        for stmt in node.body:
            depth = max(depth, _walk_stmt(stmt, 0))
        self.funcs.append((qual, self.path, node.lineno, length, depth))
        self._visit_scope(node, node.name)

    visit_FunctionDef = _func
    visit_AsyncFunctionDef = _func

    def visit_ExceptHandler(self, node):
        broad = False
        tname = ""
        if node.type is None:
            broad = True
            tname = "<bare>"
        else:
            names = []
            if isinstance(node.type, ast.Tuple):
                elts = node.type.elts
            else:
                elts = [node.type]
            for e in elts:
                if isinstance(e, ast.Name):
                    names.append(e.id)
                elif isinstance(e, ast.Attribute):
                    names.append(e.attr)
            tname = ",".join(names)
            if any(n in ("Exception", "BaseException") for n in names):
                broad = True
        if broad:
            body_src = ast.unparse(ast.Module(body=node.body, type_ignores=[]))
            has_raise = any(isinstance(n, ast.Raise) for n in ast.walk(ast.Module(body=node.body, type_ignores=[])))
            has_log = bool(
                re.search(
                    r"\b(logger|logging|log|_log|LOGGER|_logger)\.(debug|info|warning|warn|error|exception|critical|log)\b|report_exception|report_message|report_breadcrumb|capture_exception|capture_message|sentry_sdk|_report|warn_once|_warn|log_",
                    body_src,
                )
            )
            uses_exc = bool(node.name) and re.search(r"\b%s\b" % re.escape(node.name), body_src) is not None
            kind = "raise" if has_raise else ("log" if has_log else ("uses_exc" if uses_exc else "silent"))
            first = body_src.strip().splitlines()[0] if body_src.strip() else ""
            self.excepts.append((self.path, node.lineno, tname, kind, first[:120]))
        self.generic_visit(node)


def main():
    funcs = []
    excepts = []
    any_count = 0
    any_files: dict[str, int] = {}
    cast_count = 0
    cast_files: dict[str, int] = {}
    ignores = []
    for path in sorted(iter_files(ROOT)):
        rel = os.path.relpath(path, os.path.dirname(os.path.dirname(ROOT)))
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            print("SYNTAX", path, exc, file=sys.stderr)
            continue
        col = Collector(rel, src.splitlines())
        col.visit(tree)
        funcs.extend(col.funcs)
        excepts.extend(col.excepts)
        # Any as a Name or typing.Any attribute
        n_any = 0
        n_cast = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "Any":
                n_any += 1
            elif isinstance(node, ast.Attribute) and node.attr == "Any" and isinstance(node.value, ast.Name) and node.value.id in ("typing", "t"):
                n_any += 1
            elif isinstance(node, ast.Call):
                f = node.func
                if (isinstance(f, ast.Name) and f.id == "cast") or (isinstance(f, ast.Attribute) and f.attr == "cast" and isinstance(f.value, ast.Name) and f.value.id == "typing"):
                    n_cast += 1
        # subtract import lines "from typing import Any" (ImportFrom alias isn't a Name, fine)
        if n_any:
            any_files[rel] = n_any
            any_count += n_any
        if n_cast:
            cast_files[rel] = n_cast
            cast_count += n_cast
        try:
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type == tokenize.COMMENT and "type: ignore" in tok.string:
                    ignores.append((rel, tok.start[0], tok.string.strip(), src.splitlines()[tok.start[0] - 1].strip()))
        except tokenize.TokenError:
            pass

    with open(os.path.join(OUT, "py_functions.tsv"), "w") as fh:
        for qual, path, line, length, depth in funcs:
            fh.write(f"{qual}\t{path}\t{line}\t{length}\t{depth}\n")
    with open(os.path.join(OUT, "py_excepts.tsv"), "w") as fh:
        for path, line, tname, kind, first in excepts:
            fh.write(f"{path}\t{line}\t{tname}\t{kind}\t{first}\n")
    with open(os.path.join(OUT, "py_typing.txt"), "w") as fh:
        fh.write(f"Any references: {any_count} in {len(any_files)} files\n")
        for f, n in sorted(any_files.items(), key=lambda kv: -kv[1])[:30]:
            fh.write(f"  {n}\t{f}\n")
        fh.write(f"cast() calls: {cast_count} in {len(cast_files)} files\n")
        for f, n in sorted(cast_files.items(), key=lambda kv: -kv[1])[:20]:
            fh.write(f"  {n}\t{f}\n")
        fh.write(f"type: ignore comments: {len(ignores)}\n")
        for rel, line, com, code in ignores:
            fh.write(f"  {rel}:{line}\t{com}\t|| {code[:140]}\n")
    print("functions", len(funcs), "broad excepts", len(excepts))


if __name__ == "__main__":
    main()
