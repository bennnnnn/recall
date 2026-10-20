"""In test asserts of the form `X in <expr>`, how often is X an imported UPPER_CASE
constant (copy-proof) vs a string literal?"""
import ast, sys
from pathlib import Path
tests = Path(sys.argv[1])
const = lit = 0
for p in [q for q in tests.rglob("test_*.py") if "test_zz_audit" not in str(q)]:
    tree = ast.parse(p.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn)) for o in sub.ops):
                    left = sub.left
                    if isinstance(left, ast.Name) and left.id.isupper() and len(left.id) > 3:
                        const += 1
                    elif isinstance(left, ast.Attribute) and left.attr.isupper() and len(left.attr) > 3:
                        const += 1
                    elif isinstance(left, ast.Constant) and isinstance(left.value, str) and len(left.value.split()) >= 4:
                        lit += 1
print("membership asserts with an UPPER_CASE constant on the left:", const)
print("membership asserts with a >=4-word string literal on the left:", lit)
