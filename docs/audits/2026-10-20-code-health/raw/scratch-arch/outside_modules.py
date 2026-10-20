"""Read-only: apply the module public-file rule to callers OUTSIDE app/modules.

Usage: python3 -I outside_modules.py /home/user/recall-audit/apps/api/app
Parses source with ast only; imports nothing from the app.
"""

from __future__ import annotations

import ast
import sys
from collections import Counter, defaultdict
from pathlib import Path

APP = Path(sys.argv[1]).resolve()
PUBLIC_TAILS = {"api", "schemas", "service", "crud"}


def module_name(path: Path) -> str:
    parts = path.relative_to(APP.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def package_public(mod: str) -> set[str]:
    names = set(PUBLIC_TAILS)
    init = APP / "modules" / mod / "__init__.py"
    if not init.is_file():
        return names
    tree = ast.parse(init.read_text())
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if not isinstance(t, ast.Name):
                continue
            if t.id == "_EXPORTS" and isinstance(node.value, ast.Dict):
                names.update(k.value for k in node.value.keys if isinstance(k, ast.Constant))
            elif t.id in {"__all__", "_MODULE_EXPORTS"} and isinstance(
                node.value, (ast.List, ast.Tuple)
            ):
                names.update(e.value for e in node.value.elts if isinstance(e, ast.Constant))
    return names


def is_deferred(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return "deferred"
        if isinstance(cur, ast.If):
            t = cur.test
            if (isinstance(t, ast.Name) and t.id == "TYPE_CHECKING") or (
                isinstance(t, ast.Attribute) and t.attr == "TYPE_CHECKING"
            ):
                return "type_checking"
    return "load"


def main() -> None:
    files = [
        p
        for p in APP.rglob("*.py")
        if "tests" not in p.relative_to(APP).parts
        and "__pycache__" not in p.parts
        and p.relative_to(APP).parts[0] != "modules"
    ]
    edges = []  # (src_layer, src_file, line, target_module_path, symbol, verdict, when)
    for path in sorted(files):
        rel = path.relative_to(APP)
        layer = rel.parts[0] if len(rel.parts) > 1 else rel.stem
        src = path.read_text()
        tree = ast.parse(src)
        parents = {}
        for n in ast.walk(tree):
            for c in ast.iter_child_nodes(n):
                parents[c] = n
        pkg = module_name(path) if path.name == "__init__.py" else module_name(path).rpartition(".")[0]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                binds = [(a.name, None) for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    anchor = pkg.rsplit(".", node.level - 1)[0]
                    base = f"{anchor}.{base}" if base else anchor
                binds = [(base, a.name) for a in node.names]
            else:
                continue
            when = is_deferred(node, parents)
            for modname, sym in binds:
                if not modname.startswith("app.modules.") and modname != "app.modules":
                    continue
                parts = modname.removeprefix("app.modules.").split(".")
                other = parts[0]
                pub = package_public(other)
                verdict = "ok"
                if len(parts) == 1:
                    if sym is not None and (sym == "*" or sym not in pub):
                        verdict = f"PRIVATE_PKG_NAME:{sym}"
                elif parts[1] in PUBLIC_TAILS:
                    if sym and sym.startswith("_"):
                        verdict = f"PRIVATE_SYMBOL:{sym}"
                elif ".".join(parts[1:]) not in pub:
                    verdict = "INTERNAL"
                else:
                    if sym and sym.startswith("_"):
                        verdict = f"PRIVATE_SYMBOL:{sym}"
                edges.append((layer, str(rel), node.lineno, modname, sym, verdict, when))

    by_layer = Counter(e[0] for e in edges)
    bad = [e for e in edges if e[5] != "ok"]
    bad_by_layer = Counter(e[0] for e in bad)
    print("== edges from outside modules/ into app.modules (per import binding)")
    for layer, n in sorted(by_layer.items(), key=lambda x: -x[1]):
        print(f"  {layer:24s} total={n:4d} violating={bad_by_layer.get(layer, 0)}")
    print(f"  TOTAL bindings={len(edges)} violating={len(bad)}")
    files_with = defaultdict(set)
    for e in edges:
        files_with[e[0]].add(e[1])
    print("== files per layer importing modules:")
    for layer, fs in sorted(files_with.items()):
        print(f"  {layer:24s} {len(fs)}")
    print("== violations")
    for e in sorted(bad):
        print(f"  {e[1]}:{e[2]} [{e[6]}] {e[3]} {('import ' + e[4]) if e[4] else ''} -> {e[5]}")
    print("== target module internals reached (violations), by target")
    tgt = Counter(e[3] for e in bad)
    for t, n in tgt.most_common():
        print(f"  {n:3d} {t}")
    # services root (not law_binding/quota/mcp) -> modules
    print("== services/ -> modules edges (all, incl ok) by file")
    sv = defaultdict(list)
    for e in edges:
        if e[0] == "services":
            sv[e[1]].append(e)
    for f, es in sorted(sv.items()):
        tg = sorted({x[3] + (":" + x[4] if x[4] else "") for x in es})
        print(f"  {f}: {len(es)} -> {', '.join(tg)}")


main()
