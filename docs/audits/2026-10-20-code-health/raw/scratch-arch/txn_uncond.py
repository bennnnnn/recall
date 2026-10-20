"""Read-only: repository functions that commit with no way to opt out, and the callers that
compose them with other writes in one function (a multi-step unit the service cannot own).
Usage: python3 -I txn_uncond.py APP
"""

from __future__ import annotations

import ast
import sys
from collections import defaultdict
from pathlib import Path

APP = Path(sys.argv[1]).resolve()


def module_name(path: Path) -> str:
    parts = path.relative_to(APP.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def is_repo(rel: str) -> bool:
    return rel.startswith("repositories/") or (
        rel.startswith("modules/") and (rel.endswith("repository.py") or rel.endswith("lifecycle.py"))
    )


files = [p for p in APP.rglob("*.py") if "tests" not in p.relative_to(APP).parts and "__pycache__" not in p.parts]
trees = {p: ast.parse(p.read_text()) for p in files}


def commit_guarded(fn: ast.AST) -> tuple[list[int], list[int]]:
    """(unconditional commit lines, guarded commit lines)."""
    uncond, guarded = [], []

    def walk(node, under_if_commit):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            g = under_if_commit
            if isinstance(child, ast.If):
                src = ast.unparse(child.test)
                if "commit" in src:
                    walk_body(child.body, True)
                    walk_body(child.orelse, under_if_commit)
                    continue
            if isinstance(child, ast.Call):
                f = child.func
                if isinstance(f, ast.Attribute) and f.attr == "commit" and not child.args:
                    (guarded if g else uncond).append(child.lineno)
            walk(child, g)

    def walk_body(stmts, g):
        for s in stmts:
            fake = ast.Module(body=[s], type_ignores=[])
            walk(fake, g)

    walk(fn, False)
    return uncond, guarded


writes: dict[str, dict[str, str]] = defaultdict(dict)  # module -> func -> kind
for p, t in trees.items():
    rel = str(p.relative_to(APP))
    if not is_repo(rel):
        continue
    mod = module_name(p)
    for node in t.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            un, gd = commit_guarded(node)
            has_param = any(a.arg == "commit" for a in node.args.args + node.args.kwonlyargs)
            if un:
                writes[mod][node.name] = "ALWAYS_COMMITS" + ("(has commit param!)" if has_param else "")
            elif gd or has_param:
                writes[mod][node.name] = "optional"

always = {(m, f) for m, fs in writes.items() for f, k in fs.items() if k.startswith("ALWAYS")}
print("repository functions that always commit:", len(always))
for m, f in sorted(always):
    print(f"  {m}.{f}  {writes[m][f]}")


def aliases_for(tree, mod):
    pkg = mod.rpartition(".")[0]
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = pkg.rsplit(".", node.level - 1)[0]
                base = f"{anchor}.{base}" if base else anchor
            for a in node.names:
                out[a.asname or a.name] = f"{base}.{a.name}"
        elif isinstance(node, ast.Import):
            for a in node.names:
                out[a.asname or a.name.split(".")[0]] = a.name
    return out


def target(call, aliases, mod):
    f = call.func
    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
        tm = aliases.get(f.value.id)
        if tm in writes and f.attr in writes[tm]:
            return tm, f.attr
    if isinstance(f, ast.Name):
        full = aliases.get(f.id)
        if full:
            m, _, fn = full.rpartition(".")
            if m in writes and fn in writes[m]:
                return m, fn
        if mod in writes and f.id in writes[mod]:
            return mod, f.id
    return None


def passes_false(call):
    return any(kw.arg == "commit" and isinstance(kw.value, ast.Constant) and kw.value.value is False for kw in call.keywords)


print("\n== callers composing an always-committing repository write with another write")
for p, t in sorted(trees.items()):
    rel = str(p.relative_to(APP))
    mod = module_name(p)
    al = aliases_for(t, mod)
    for fn in ast.walk(t):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = []
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                tg = target(node, al, mod)
                if tg:
                    calls.append((node.lineno, tg, passes_false(node)))
                f = node.func
                if isinstance(f, ast.Attribute) and f.attr == "commit" and not node.args and not is_repo(rel):
                    calls.append((node.lineno, ("session", "commit"), False))
        if len(calls) < 2:
            continue
        calls.sort()
        bad = [c for c in calls[:-1] if c[1] in always]
        if bad:
            print(f"- {rel}:{fn.lineno} {fn.name}()")
            for c in calls:
                tag = "ALWAYS-COMMITS" if c[1] in always else ("commit=False" if c[2] else "")
                print(f"     line {c[0]}: {c[1][0].split('.')[-1]}.{c[1][1]} {tag}")
