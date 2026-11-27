"""Tests check which prompt text a turn gets, not its wording (code-health audit TEST-06).

An assert that pastes a prompt's words (``assert "Never use decorative headings" in
system``) turns red on every rewording of that prompt, and its fix is pasting the new
words, so it pins copy rather than behaviour. Assert the constant instead
(``assert EMAIL_DRAFT_HINT in system``), or use the golden test's ``@NAME`` tokens
(``modules/chat/test_prompt_golden.py``).

A phrase that must survive any rewording, a safety promise such as "Never say you
sent", stays literal with ``# safety phrase`` on its line. The rest are counted here
and may only go down.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator

from .boundary_support import APP_ROOT

_TESTS = APP_ROOT / "tests"
_PLACEHOLDER = re.compile(r"(?<!\{)\{[A-Za-z_0-9!:.]*\}(?!\})")
# Literal prompt-copy asserts left; lower this when a change replaces some. 107 since the
# guard reads templates too (2026-11-10): nine asserts on template copy were already there;
# 105 once the maths fence tests stopped pinning the dropped "could not render" note; 104 once
# the privacy test stopped pinning the scanner's old "Recall does not keep that photo"; 103
# once the lesson shape's parts became constants of their own (2026-11-14); 102 once the old
# ending rule ("a question or an offer") was replaced and its pin with it (2026-11-20); 106
# once the guard read constants built from named parts (``_folded``), which four older pins on
# such copy had escaped, as the format and privacy rules split into parts would have (2026-11-22);
# 86 once the day reflection test asserted its constant (2026-11-27).
_PINNED = 86


def _as_sent(text: str) -> str:
    """A template as a model reads it: each ``{placeholder}`` filled (with nothing) and each
    ``{{`` brace single. A test that pinned a template's words went unseen while templates
    were skipped (the turn's read, 2026-11-10)."""
    return _PLACEHOLDER.sub("", text).replace("{{", "{").replace("}}", "}")


def _folded(value: ast.expr | None, known: dict[str, str]) -> str | None:
    """A module-level string as written: a literal, or one built from the module's earlier
    constants (``f"{PRIVACY_CONTEXT_HINT}\\n…"``), so copy split into named parts is still read."""
    if isinstance(value, ast.Constant):
        return value.value if isinstance(value.value, str) else None
    if isinstance(value, ast.Name):
        return known.get(value.id)
    if isinstance(value, ast.JoinedStr):
        parts = []
        for part in value.values:
            inner = part.value if isinstance(part, ast.FormattedValue) else part
            folded = _folded(inner, known)
            if folded is None or (isinstance(part, ast.FormattedValue) and part.format_spec):
                return None
            parts.append(folded)
        return "".join(parts)
    return None


def _prompt_texts() -> list[str]:
    """Every module-level string constant in app/ long enough to be prompt copy."""
    texts: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        if _TESTS in path.parents:
            continue
        known: dict[str, str] = {}
        for node in ast.parse(path.read_text()).body:
            target: ast.expr
            value: ast.expr | None
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign):
                target, value = node.target, node.value
            else:
                continue
            text = _folded(value, known)
            if text is None:
                continue
            if isinstance(target, ast.Name):
                known[target.id] = text
            if len(text) >= 40:
                texts.append(_as_sent(text))
    return texts


def _pinned_copy() -> Iterator[str]:
    texts = _prompt_texts()
    lowered = [text.lower() for text in texts]
    for path in sorted(_TESTS.rglob("test_*.py")):
        source = path.read_text()
        lines = source.splitlines()
        for node in ast.walk(ast.parse(source)):
            if not (isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare)):
                continue
            left = node.test.left
            if not (isinstance(left, ast.Constant) and isinstance(left.value, str)):
                continue
            phrase = left.value
            if len(phrase) < 25 and len(phrase.split()) < 4:
                continue
            if any("# safety phrase" in line for line in lines[node.lineno - 1 : node.end_lineno]):
                continue
            haystack = lowered if phrase == phrase.lower() else texts
            if any(phrase in text for text in haystack):
                yield f"{path.relative_to(_TESTS)}:{node.lineno} {phrase[:60]!r}"


def test_prompt_copy_asserts_only_go_down() -> None:
    pinned = list(_pinned_copy())
    assert len(pinned) <= _PINNED, "assert the prompt constant, not its words:\n" + "\n".join(
        pinned
    )
    assert len(pinned) == _PINNED, f"fewer pinned phrases now: set _PINNED = {len(pinned)}"
