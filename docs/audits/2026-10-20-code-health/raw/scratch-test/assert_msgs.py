"""With --assert=plain, a failing bare `assert a == b` prints only AssertionError.
Count asserts that compare values and carry no message."""
import ast, sys
from pathlib import Path
tests = Path(sys.argv[1])
total = with_msg = compare_no_msg = 0
for p in [q for q in tests.rglob("*.py") if "test_zz_audit" not in str(q)]:
    try:
        tree = ast.parse(p.read_text())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            total += 1
            if node.msg is not None:
                with_msg += 1
            elif isinstance(node.test, ast.Compare):
                compare_no_msg += 1
print(f"assert statements: {total}; with a message: {with_msg} ({with_msg*100//total}%); "
      f"comparisons without a message: {compare_no_msg} ({compare_no_msg*100//total}%)")
