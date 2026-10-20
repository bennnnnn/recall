"""Read-only: transaction-ownership check (CLAUDE.md "Transaction ownership").

1. Writers: functions with a ``commit`` parameter (default True) -> they commit unless told not to.
2. For each production function, the writer calls it makes, and whether each passes commit=False.
3. Flags a function that makes 2+ DB writes where a write that is NOT the last one commits
   (a partial commit inside a multi-step unit), or that mixes committing writes with its own
   ``session.commit()``.
4. Lists unconditional ``.commit()`` / ``.rollback()`` calls by layer.
Usage: python3 -I txn_owner.py APP
"""

from __future__ import annotations

import ast
import sys
from collections import Counter, defaultdict
from pathlib import Path

APP = Path(sys.argv[1]).resolve()


def module_name(path: Path) -> str:
    parts = path.relative_to(APP.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


files = [
    p for p in APP.rglob("*.py") if "tests" not in p.relative_to(APP).parts and "__pycache__" not in p.parts
]
trees = {p: ast.parse(p.read_text()) for p in files}

# 1. writers
writers: dict[str, set[str]] = defaultdict(set)  # module -> {func}
for p, t in trees.items():
    mod = module_name(p)
    for node in ast.walk(t):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            allargs = args.args + args.kwonlyargs
            defaults = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults) + list(
                args.kw_defaults
            )
            for a, d in zip(allargs, defaults):
                if a.arg == "commit" and isinstance(d, ast.Constant) and d.value is True:
                    writers[mod].add(node.name)
writer_names = {f for fs in writers.values() for f in fs}
print("writer functions (commit=True default):", sum(len(v) for v in writers.values()))
for m, fs in sorted(writers.items()):
    print(f"  {m}: {sorted(fs)}")


def resolve_aliases(tree: ast.Module, mod: str) -> dict[str, str]:
    """local name -> module path for imported modules, or module.func for imported functions."""
    pkg = mod.rpartition(".")[0]
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = (mod if False else pkg).rsplit(".", node.level - 1)[0]
                base = f"{anchor}.{base}" if base else anchor
            for a in node.names:
                out[a.asname or a.name] = f"{base}.{a.name}"
        elif isinstance(node, ast.Import):
            for a in node.names:
                out[a.asname or a.name.split(".")[0]] = a.name
    return out


def call_target(call: ast.Call, aliases: dict[str, str], mod: str) -> tuple[str, str] | None:
    f = call.func
    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
        target_mod = aliases.get(f.value.id)
        if target_mod and target_mod in writers and f.attr in writers[target_mod]:
            return target_mod, f.attr
    if isinstance(f, ast.Name):
        full = aliases.get(f.id)
        if full:
            m, _, fn = full.rpartition(".")
            if m in writers and fn in writers[m]:
                return m, fn
        if mod in writers and f.id in writers[mod]:
            return mod, f.id
    return None


def commit_kw(call: ast.Call) -> str:
    for kw in call.keywords:
        if kw.arg == "commit":
            if isinstance(kw.value, ast.Constant):
                return "False" if kw.value.value is False else "True"
            return "passthrough"
        if kw.arg is None:
            return "kwargs"
    return "default(True)"


flags = []
commit_calls = Counter()
commit_sites = defaultdict(list)
for p, t in trees.items():
    mod = module_name(p)
    rel = str(p.relative_to(APP))
    aliases = resolve_aliases(t, mod)
    for fn in ast.walk(t):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = []
        own_commit = []
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                tgt = call_target(node, aliases, mod)
                if tgt:
                    calls.append((node.lineno, tgt, commit_kw(node)))
                f = node.func
                if isinstance(f, ast.Attribute) and f.attr in ("commit", "rollback") and not node.args:
                    own_commit.append((node.lineno, f.attr))
        for ln, kind in own_commit:
            layer = rel.split("/")[0] if "/" in rel else rel
            sub = rel.split("/")[1] if rel.startswith("modules/") else ""
            commit_calls[(layer, kind)] += 1
            commit_sites[kind].append(f"{rel}:{ln} in {fn.name}")
        if len(calls) >= 2 or (calls and own_commit):
            calls.sort()
            committing_not_last = [c for c in calls[:-1] if c[2] == "default(True)"]
            mixed = own_commit and any(c[2] == "default(True)" for c in calls)
            if committing_not_last or mixed:
                flags.append((rel, fn.name, fn.lineno, calls, own_commit))

print("\n== functions with a committing write followed by another write, or mixed with own commit")
for rel, name, ln, calls, own in sorted(flags):
    print(f"- {rel}:{ln} {name}()")
    for c in calls:
        print(f"     line {c[0]}: {c[1][0].split('.')[-1]}.{c[1][1]}  commit={c[2]}")
    for o in own:
        print(f"     line {o[0]}: session.{o[1]}()")
print("\n== .commit()/.rollback() call counts by top dir")
for k, v in sorted(commit_calls.items()):
    print(f"  {k}: {v}")
