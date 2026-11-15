"""No log line at INFO or above carries what the user wrote.

INFO and above reach the log drain and Sentry (breadcrumbs, and events from ERROR), where
retention and access differ from the database's. A reminder's title went out as
``title=%s`` and a reminder email's subject, the reminder itself, as ``subject=%r``. A log
call says how much instead: ``title_chars=%d`` with ``len(title)``, ids and kinds.

The check reads each logger call's arguments for a name that holds user or model text.
``len()``, ``type()`` and ``.__name__`` around it are fine, and so is a provider's error
body (``response.text``), which is the provider's words, not the user's.
"""

from __future__ import annotations

import ast
import re

from .boundary_support import APP_ROOT

_LEVELS = frozenset({"info", "warning", "warn", "error", "exception", "critical"})
_TEXT_NAMES = re.compile(
    r"^(?:content|title|subject|text|prompt|query|transcript|question|summary|snippet|caption"
    r"|reply|answer|message|instruction|expr|expression|fact|note|description|raw|html"
    # A name (the user's, a compound's, a place's) and a structure or formula they typed.
    r"|name|smiles|formula|reading)$"
    r"|_(?:content|title|subject|text|prompt|query|transcript|question|summary|reply|answer)$",
    re.IGNORECASE,
)
_WRAPPERS_THAT_HIDE = frozenset({"len", "type", "bool", "id", "isinstance"})
# Escapes its argument onto one line (``core/log_text``): the argument is still logged, whole.
_WRAPPERS_THAT_KEEP = frozenset({"log_safe"})
_PROVIDER_RESPONSES = frozenset({"response", "resp"})
# (file, name): why the name holds no user text there.
_ALLOWED = {
    ("services/scan_read.py", "subject"): "the STEM subject's name: maths, physics, chemistry",
    ("services/subjects/guard.py", "subject"): "the subject's name: maths, physics, chemistry",
    ("services/subjects/order.py", "subject"): "the subject's name: maths, physics, chemistry",
    ("services/subjects/order.py", "name"): "the step of the order that failed",
    ("background/handlers.py", "raw"): "a job payload's malformed user id",
    ("gateways/revenuecat_gateway.py", "raw"): "a RevenueCat webhook field (a timestamp)",
    ("background/periodic.py", "name"): "a scheduler's name",
    ("core/readings.py", "name"): "a reading function's name",
    ("modules/chat/finalize_passes.py", "name"): "a finalize pass's name",
    ("modules/chat/post_turn.py", "name"): "a post-turn job's name",
    ("modules/chat/tool_loop/calls.py", "name"): "the called tool's name",
    ("modules/speech/live_talk_tools.py", "name"): "the called tool's name",
    ("process_bootstrap.py", "name"): "a shutdown step's name",
}


def _names(node: ast.AST) -> set[str]:
    """Identifiers an argument reads, leaving out what a wrapper reduces to a size or a type."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in _WRAPPERS_THAT_HIDE:
            return set()
        if node.func.id in _WRAPPERS_THAT_KEEP:
            return set().union(*(_names(arg) for arg in node.args))
    if isinstance(node, ast.Attribute):
        if node.attr == "__name__":
            return set()
        if isinstance(node.value, ast.Name) and node.value.id in _PROVIDER_RESPONSES:
            return set()
        return {node.attr} | _names(node.value)
    if isinstance(node, ast.Name):
        return {node.id}
    found: set[str] = set()
    for child in ast.iter_child_nodes(node):
        found |= _names(child)
    return found


def _is_log_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _LEVELS
        and "log" in ast.unparse(node.func.value).lower()
        and bool(node.args)
    )


def test_no_log_line_carries_user_text() -> None:
    leaks = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        relative = path.relative_to(APP_ROOT).as_posix()
        if relative.startswith("tests/"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not _is_log_call(node):
                continue
            assert isinstance(node, ast.Call)
            for name in sorted({name for arg in node.args[1:] for name in _names(arg)}):
                if _TEXT_NAMES.search(name) and (relative, name) not in _ALLOWED:
                    leaks.append(f"{relative}:{node.lineno} logs {name}")
    assert not leaks, "log its length or an id instead:\n" + "\n".join(leaks)


# ``%r`` prints a string whole, quotes and all: what each argument a ``%r`` may print is, by
# name. "RDKit validate failed for %r" printed a SMILES the user typed as ``cleaned``, a name
# the text check cannot know (review, 2026-11-13).
_REPR_NAMES = {
    "exc": "an exception (its class and message)",
    "exception": "a task's exception",
    "cancelled": "a task's state",
    "task": "an asyncio task",
    "key": "a Redis key",
    "marker_key": "a Redis key",
    "user_id": "an id",
    "terminal_image_message_id": "an id",
    "ctx": "the stream context holding that id",
    "raw": "a job payload's malformed user id",
    "payload": "a job payload's malformed user id",
    "get": "a payload read (``payload.get``)",
    "name": "a shutdown step's name",
}


def test_a_repr_in_a_log_line_prints_no_user_text() -> None:
    unnamed = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        relative = path.relative_to(APP_ROOT).as_posix()
        if relative.startswith("tests/"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not _is_log_call(node):
                continue
            assert isinstance(node, ast.Call)
            template = node.args[0]
            if not (isinstance(template, ast.Constant) and "%r" in str(template.value)):
                continue
            for name in sorted({name for arg in node.args[1:] for name in _names(arg)}):
                if name not in _REPR_NAMES:
                    unnamed.append(f"{relative}:{node.lineno} prints {name} with %r")
    assert not unnamed, "log its length or kind, or name it in _REPR_NAMES:\n" + "\n".join(unnamed)


def test_the_check_sees_a_leak_and_passes_a_length() -> None:
    def leaked(source: str) -> set[str]:
        call = ast.parse(source).body[0]
        assert isinstance(call, ast.Expr) and _is_log_call(call.value)
        assert isinstance(call.value, ast.Call)
        return {n for arg in call.value.args[1:] for n in _names(arg) if _TEXT_NAMES.search(n)}

    assert leaked('logger.info("saved title=%s", title[:80])') == {"title"}
    assert leaked('logger.exception("failed subject=%r", email.subject)') == {"subject"}
    assert leaked('logger.info("saved title_chars=%d", len(title))') == set()
    assert leaked('logger.info("skipped: %s", type(exc).__name__)') == set()
    assert leaked('logger.warning("failed body=%s", response.text[:500])') == set()
    assert leaked('logger.info("saved title=%s", log_safe(title))') == {"title"}
    # The ``%r`` check reads what ``log_safe`` prints, not the function's own name.
    assert _names(ast.parse("log_safe(key)", mode="eval").body) == {"key"}
