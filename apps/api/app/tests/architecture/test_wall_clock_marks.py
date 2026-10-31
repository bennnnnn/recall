"""Every test that asserts on the wall clock carries ``@pytest.mark.wall_clock``.

CI runs the suite on one worker per core, then the ``wall_clock`` tests alone: a duration
measured while three other workers share the machine is not the one the test was written
for (a 0.5 s budget took 0.68 s). A test asserts on the clock when an assert reads it
(``time.perf_counter()``, ``time.monotonic()``, ``time.time()``, their ``_ns`` forms and
``process_time``), reads a name assigned from such a read, or calls a function of the same
file that reads it. The mark may sit on the test, its class, or the module's ``pytestmark``.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
_CLOCK_READS = frozenset(
    {"perf_counter", "perf_counter_ns", "monotonic", "monotonic_ns", "process_time"}
)
_TIME_READS = frozenset({"time", "time_ns"})


def _is_clock_read(call: ast.Call, helpers: frozenset[str]) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute):
        if func.attr in _CLOCK_READS:
            return True
        owner = func.value
        return func.attr in _TIME_READS and isinstance(owner, ast.Name) and owner.id == "time"
    if isinstance(func, ast.Name):
        return func.id in _CLOCK_READS or func.id in _TIME_READS or func.id in helpers
    return False


def _reads_clock(node: ast.AST, helpers: frozenset[str] = frozenset()) -> bool:
    return any(isinstance(sub, ast.Call) and _is_clock_read(sub, helpers) for sub in ast.walk(node))


def _marked(decorators: list[ast.expr]) -> bool:
    return any("wall_clock" in ast.unparse(decorator) for decorator in decorators)


def _module_marked(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets)
        and "wall_clock" in ast.unparse(node.value)
        for node in tree.body
    )


def _asserts_on_clock(
    test: ast.FunctionDef | ast.AsyncFunctionDef, helpers: frozenset[str]
) -> bool:
    timed: set[str] = set()
    for node in ast.walk(test):
        if isinstance(node, ast.Assign | ast.AnnAssign | ast.AugAssign) and node.value is not None:
            if _reads_clock(node.value, helpers):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                timed |= {n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)}
    return any(
        isinstance(node, ast.Assert)
        and (
            _reads_clock(node.test, helpers)
            or bool({n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)} & timed)
        )
        for node in ast.walk(test)
    )


def unmarked_wall_clock_tests() -> list[str]:
    missing: list[str] = []
    for path in sorted(TESTS.rglob("test_*.py")):
        tree = ast.parse(path.read_text())
        if _module_marked(tree):
            continue
        helpers = frozenset(
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and not node.name.startswith("test_")
            and _reads_clock(node)
        )
        scopes: list[tuple[list[ast.expr], list[ast.stmt]]] = [([], tree.body)]
        scopes += [(n.decorator_list, n.body) for n in tree.body if isinstance(n, ast.ClassDef)]
        for class_marks, body in scopes:
            for node in body:
                if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                if not node.name.startswith("test_") or _marked(class_marks):
                    continue
                if _asserts_on_clock(node, helpers) and not _marked(node.decorator_list):
                    missing.append(f"{path.relative_to(TESTS)}::{node.name}")
    return missing


def test_every_test_that_times_itself_runs_alone_in_ci() -> None:
    missing = unmarked_wall_clock_tests()
    assert not missing, (
        "asserts on the wall clock, so it runs alone in CI: add @pytest.mark.wall_clock\n  "
        + "\n  ".join(missing)
    )


def test_the_check_sees_a_timed_assert_and_its_helpers() -> None:
    tree = ast.parse(
        "import time\n"
        "def _took(fn):\n    start = time.perf_counter(); fn(); return time.perf_counter() - start\n"
        "def test_direct():\n    t0 = time.monotonic()\n    assert time.monotonic() - t0 < 1\n"
        "def test_named():\n    elapsed = _took(print)\n    assert elapsed < 1\n"
        "def test_plain():\n    now = 3\n    assert now < 4\n"
    )
    helpers = frozenset({"_took"})
    tests = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert _asserts_on_clock(tests["test_direct"], helpers)
    assert _asserts_on_clock(tests["test_named"], helpers)
    assert not _asserts_on_clock(tests["test_plain"], helpers)
