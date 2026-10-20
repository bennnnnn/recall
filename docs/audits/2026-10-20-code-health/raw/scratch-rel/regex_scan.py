"""Collect literal regex patterns used with the re module in apps/api/app (non-test).

Prints file:line, flags, and the pattern, for patterns with nested quantifiers
(a quantified group whose body itself contains an unbounded quantifier), which
is the classic catastrophic-backtracking shape.
"""
import ast
import sys
import re
import sre_parse
from pathlib import Path

ROOT = Path(sys.argv[1])
RE_FUNCS = {"compile", "search", "match", "fullmatch", "sub", "subn", "findall", "finditer", "split"}

def const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a = const_str(node.left); b = const_str(node.right)
        if a is not None and b is not None:
            return a + b
    return None

MAXREPEAT = sre_parse.MAXREPEAT

def unbounded(op, av):
    return op in (sre_parse.MAX_REPEAT, sre_parse.MIN_REPEAT) and av[1] == MAXREPEAT

def contains_unbounded(sub):
    for op, av in sub:
        if op in (sre_parse.MAX_REPEAT, sre_parse.MIN_REPEAT):
            if av[1] == MAXREPEAT or av[1] > 50:
                return True
            if contains_unbounded(av[2]):
                return True
        elif op == sre_parse.SUBPATTERN:
            if contains_unbounded(av[3]):
                return True
        elif op == sre_parse.BRANCH:
            for b in av[1]:
                if contains_unbounded(b):
                    return True
        elif op in (sre_parse.ASSERT, sre_parse.ASSERT_NOT):
            pass
    return False

def nested(sub, depth=0):
    hits = []
    for op, av in sub:
        if op in (sre_parse.MAX_REPEAT, sre_parse.MIN_REPEAT):
            lo, hi, body = av
            if (hi == MAXREPEAT or hi > 50) and contains_unbounded(body):
                hits.append("nested-quantifier")
            hits += nested(body, depth+1)
        elif op == sre_parse.SUBPATTERN:
            hits += nested(av[3], depth+1)
        elif op == sre_parse.BRANCH:
            for b in av[1]:
                hits += nested(b, depth+1)
        elif op in (sre_parse.ASSERT, sre_parse.ASSERT_NOT):
            hits += nested(av[1], depth+1)
    return hits

count = 0
for p in sorted(ROOT.rglob("*.py")):
    if "/tests/" in str(p):
        continue
    try:
        tree = ast.parse(p.read_text())
    except Exception:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr in RE_FUNCS and isinstance(f.value, ast.Name) and f.value.id in ("re", "regex")):
            continue
        if not node.args:
            continue
        pat = const_str(node.args[0])
        if pat is None:
            continue
        count += 1
        try:
            parsed = sre_parse.parse(pat)
        except Exception as e:
            continue
        hits = nested(list(parsed))
        if hits:
            rel = p.relative_to(ROOT.parent.parent.parent)
            print(f"{rel}:{node.lineno}: {pat!r}")
print("TOTAL literal patterns:", count, file=sys.stderr)
