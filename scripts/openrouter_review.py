#!/usr/bin/env python3
"""Ask a non-Anthropic model on OpenRouter to review a change, or a slice of the code.

Two uses, one prompt:

  PR review (GitHub Actions, .github/workflows/openrouter-review.yml):
    openrouter_review.py pr --model deepseek/deepseek-v4-pro --base <sha> --head <sha> \
        --out review.md
  Whole-code audit, run by hand a module at a time:
    openrouter_review.py paths --model z-ai/glm-5.3 apps/api/app/modules/money --out money.md

The model gets the project's rules (CLAUDE.md, docs/ENGINEERING_STANDARDS.md) and the code,
and answers with findings in JSON, each one a concrete input or sequence that breaks the
code. Findings are advice: a model on its own gets many wrong, so every one is checked
against the code before anything is changed. Standard library only, so the workflow installs
nothing. The key is read from OPENROUTER_API_KEY and never written anywhere.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://openrouter.ai/api/v1/chat/completions"
RULE_FILES = ("CLAUDE.md", "docs/ENGINEERING_STANDARDS.md")
# What is sent: a 1M-token model takes far more, but a review past this is unfocused.
MAX_CODE_CHARS = 1_200_000
MAX_FILE_CHARS = 120_000
CODE_SUFFIXES = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".yml",
    ".yaml",
    ".json",
    ".md",
    ".sql",
)
SKIP_PARTS = (
    "node_modules",
    "__pycache__",
    ".venv",
    "vendor",
    "generated",
    "dist",
    "build",
)
TIMEOUT_SECONDS = 600
MAX_OUTPUT_TOKENS = 64_000
# How each model reasons. DeepSeek V4 Pro on OpenRouter spent 109,002 of 131,072 output tokens
# reasoning over one small module and never wrote its answer, and it overshot every cap tried
# (24,550 of a 16,000-token cap; 62k at "medium", 58k at "low"): it answers with reasoning off.
REASONING: dict[str, dict[str, object]] = {
    "deepseek/deepseek-v4-pro": {"enabled": False},
}
DEFAULT_REASONING: dict[str, object] = {"effort": "medium"}

PROMPT = """You review code for Recall, a mobile AI chat app (Expo React Native + FastAPI).
The project's rules follow, then the code to review. Find real defects only:
- a wrong result, a crash, a hang, a race, a security hole, data loss;
- a clear violation of the project rules (layers, golden rules, no duplicate code: the same
  logic written twice is a defect, because this code will be forked into a second app);
- for maths/physics/chemistry: a verified answer that can be wrong is the worst defect.
For each finding name the exact input or sequence that triggers it. Skip style, naming,
missing comments and speculation you cannot tie to a concrete input. Fewer, real findings
beat many guesses.

Answer with JSON only, no prose around it:
{"findings": [{"file": "path", "line": 123, "severity": "high|medium|low",
 "title": "short", "trigger": "the input or sequence", "why": "what goes wrong",
 "fix": "one-line class fix"}]}
"""


def _read(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    if len(text) > MAX_FILE_CHARS:
        return text[:MAX_FILE_CHARS] + "\n… (cut for length)\n"
    return text


def _rules() -> str:
    return "\n\n".join(f"===== {name}\n{_read(ROOT / name)}" for name in RULE_FILES)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def _wanted(path: Path) -> bool:
    return path.suffix in CODE_SUFFIXES and not any(
        part in SKIP_PARTS for part in path.parts
    )


def _bundle(paths: list[Path]) -> str:
    parts: list[str] = []
    used = 0
    for path in paths:
        body = _read(ROOT / path)
        if not body:
            continue
        piece = f"===== {path}\n{body}"
        if used + len(piece) > MAX_CODE_CHARS:
            parts.append(
                f"===== (stopped: more files than fit; {path} and after left out)"
            )
            break
        parts.append(piece)
        used += len(piece)
    return "\n\n".join(parts)


def pr_material(base: str, head: str) -> str:
    diff = _git("diff", "--unified=5", f"{base}...{head}")
    changed = [Path(p) for p in _git("diff", "--name-only", f"{base}...{head}").split()]
    files = _bundle([p for p in changed if _wanted(p) and (ROOT / p).exists()])
    return (
        f"THE DIFF\n{diff[: MAX_CODE_CHARS // 2]}\n\nTHE CHANGED FILES IN FULL\n{files}"
    )


def paths_material(targets: list[str]) -> str:
    files: list[Path] = []
    for target in targets:
        root = ROOT / target
        found = [root] if root.is_file() else sorted(root.rglob("*"))
        files += [p.relative_to(ROOT) for p in found if p.is_file() and _wanted(p)]
    return f"THE CODE\n{_bundle(files)}"


def ask(model: str, material: str) -> dict:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"{_rules()}\n\n{material}"},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "reasoning": REASONING.get(model, DEFAULT_REASONING),
    }
    request = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            reply = json.load(response)
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            f"OpenRouter answered {exc.code}: {exc.read()[:300]!r}"
        ) from exc
    choice = reply["choices"][0]
    text = choice["message"].get("content") or ""
    if not text.strip() or choice.get("finish_reason") == "length":
        # Out of output before the answer: say so, never "0 findings".
        return {
            "findings": [],
            "unparsed": f"(no answer: finish_reason {choice.get('finish_reason')})",
            "usage": reply.get("usage", {}),
        }
    start, end = text.find("{"), text.rfind("}")
    try:
        found = json.loads(text[start : end + 1]) if start >= 0 else {}
    except json.JSONDecodeError:
        found = {"findings": [], "unparsed": text[:4000]}
    found["usage"] = reply.get("usage", {})
    return found


def markdown(model: str, found: dict) -> str:
    findings = found.get("findings") or []
    usage = found.get("usage") or {}
    lines = [
        f"### {model} review (advisory)",
        "",
        f"{len(findings)} finding(s); every one is checked against the code before any change.",
        "",
    ]
    order = {"high": 0, "medium": 1, "low": 2}
    for item in sorted(findings, key=lambda f: order.get(str(f.get("severity")), 3)):
        where = f"`{item.get('file', '?')}:{item.get('line', '?')}`"
        lines += [
            f"- **{item.get('severity', '?')}** {where} {item.get('title', '')}",
            f"  - trigger: {item.get('trigger', '')}",
            f"  - why: {item.get('why', '')}",
            f"  - fix: {item.get('fix', '')}",
        ]
    if found.get("unparsed"):
        lines += [
            "",
            "The model's answer was not JSON:",
            "",
            "```",
            found["unparsed"],
            "```",
        ]
    tokens = f"{usage.get('prompt_tokens', '?')} in / {usage.get('completion_tokens', '?')} out tokens"
    if usage.get("cost") is not None:
        tokens += f", ${usage['cost']:.3f}"
    lines += ["", f"<sub>{tokens}</sub>"]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    pr = sub.add_parser("pr")
    pr.add_argument("--base", required=True)
    pr.add_argument("--head", required=True)
    paths = sub.add_parser("paths")
    paths.add_argument("targets", nargs="+")
    for each in (pr, paths):
        each.add_argument("--model", required=True)
        each.add_argument("--out", required=True)
        each.add_argument("--json", help="also write the raw findings here")
    args = parser.parse_args()
    material = (
        pr_material(args.base, args.head)
        if args.mode == "pr"
        else paths_material(args.targets)
    )
    found = ask(args.model, material)
    Path(args.out).write_text(markdown(args.model, found), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps(found, indent=1), encoding="utf-8")
    print(
        f"{len(found.get('findings') or [])} findings from {args.model}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
