"""Count test assertions pinned to prompt copy.

A "pinned" assertion is `assert "<literal>" in X` / `not in` / `==` where the
literal (>= 4 words or >= 25 chars) appears verbatim (case-insensitive) in an app
module whose name says it holds prompt text (prompt_constants/, *prompt*.py,
teaching, routing copy ...). Prints totals and the files with most pins.
"""
import ast
import collections
import re
import sys
from pathlib import Path

api = Path(sys.argv[1])
app = api / "app"
tests = app / "tests"

# Build the corpus of string constants in non-test app code, split by "prompt-ish" or not.
prompt_files = []
for p in [q for q in app.rglob("*.py") if "test_zz_audit" not in str(q)]:
    if "tests" in p.parts:
        continue
    rel = str(p.relative_to(api))
    if "prompt" in rel or "/prompts" in rel:
        prompt_files.append(p)

def strings_of(path):
    out = []
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    out.append(v.value)
    return out

prompt_corpus = "\n".join(s for p in prompt_files for s in strings_of(p)).lower()
# normalize whitespace
prompt_corpus_ws = re.sub(r"\s+", " ", prompt_corpus)

def is_copy(s):
    s2 = re.sub(r"\s+", " ", s.strip().lower())
    if len(s2.split()) < 4 and len(s2) < 25:
        return False
    return s2 in prompt_corpus_ws

pins = collections.Counter()
total_asserts = 0
examples = collections.defaultdict(list)
for path in tests.rglob("test_*.py"):
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            total_asserts += 1
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Compare) and isinstance(sub.left, ast.Constant) and isinstance(sub.left.value, str):
                    if any(isinstance(op, (ast.In, ast.NotIn)) for op in sub.ops):
                        if is_copy(sub.left.value):
                            rel = str(path.relative_to(api))
                            pins[rel] += 1
                            if len(examples[rel]) < 2:
                                examples[rel].append((node.lineno, sub.left.value[:70]))
print("prompt-ish source files:", len(prompt_files))
print("assert statements scanned:", total_asserts)
print("asserts pinned to verbatim prompt copy:", sum(pins.values()), "in", len(pins), "files")
for f, n in pins.most_common(12):
    print(f"  {n:4d} {f}  e.g. line {examples[f][0][0]}: {examples[f][0][1]!r}")
