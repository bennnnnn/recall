"""Like regex_scan.py but also reconstructs f-string patterns (placeholders -> 'Q')
and module-level string constants that are later compiled. Prints nested-quantifier hits."""
import ast, sys, warnings
warnings.filterwarnings("ignore")
import sre_parse
from pathlib import Path

ROOT = Path(sys.argv[1])
RE_FUNCS = {"compile", "search", "match", "fullmatch", "sub", "subn", "findall", "finditer", "split"}
MAXREPEAT = sre_parse.MAXREPEAT

def const_str(node, env):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(v.value)
            elif isinstance(v, ast.FormattedValue):
                inner = const_str(v.value, env)
                out.append(f"(?:{inner})" if inner is not None else "Q")
        return "".join(out)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a = const_str(node.left, env); b = const_str(node.right, env)
        if a is not None and b is not None:
            return a + b
    return None

def contains_unbounded(sub):
    for op, av in sub:
        if op in (sre_parse.MAX_REPEAT, sre_parse.MIN_REPEAT):
            if av[1] == MAXREPEAT or av[1] > 50:
                return True
            if contains_unbounded(av[2]): return True
        elif op == sre_parse.SUBPATTERN:
            if contains_unbounded(av[3]): return True
        elif op == sre_parse.BRANCH:
            if any(contains_unbounded(b) for b in av[1]): return True
    return False

def nested(sub):
    hits = 0
    for op, av in sub:
        if op in (sre_parse.MAX_REPEAT, sre_parse.MIN_REPEAT):
            lo, hi, body = av
            if (hi == MAXREPEAT or hi > 50) and contains_unbounded(body):
                hits += 1
            hits += nested(body)
        elif op == sre_parse.SUBPATTERN:
            hits += nested(av[3])
        elif op == sre_parse.BRANCH:
            for b in av[1]: hits += nested(b)
        elif op in (sre_parse.ASSERT, sre_parse.ASSERT_NOT):
            hits += nested(av[1])
    return hits

seen = set()
for p in sorted(ROOT.rglob("*.py")):
    if "/tests/" in str(p): continue
    try: tree = ast.parse(p.read_text())
    except Exception: continue
    env = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            s = const_str(node.value, env)
            if s is not None: env[node.targets[0].id] = s
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            s = const_str(node.value, env)
            if s is not None: env[node.target.id] = s
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call): continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr in RE_FUNCS and isinstance(f.value, ast.Name) and f.value.id == "re"):
            continue
        if not node.args: continue
        if isinstance(node.args[0], ast.Constant):
            continue  # covered by regex_scan.py
        pat = const_str(node.args[0], env)
        if pat is None: continue
        try: parsed = sre_parse.parse(pat)
        except Exception: continue
        if nested(list(parsed)):
            rel = p.relative_to(ROOT.parent.parent.parent)
            key = (str(rel), node.lineno)
            if key in seen: continue
            seen.add(key)
            print(f"{rel}:{node.lineno}: {f.attr}: {pat[:300]!r}")
