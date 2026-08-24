"""Deterministic server-owned output blocks for verified math turns.

The LLM is responsible for explanation prose, not for serializing Recall's
answer/graph/geometry UI protocol. Verified math tools already computed the
canonical values before generation, so finalization replaces any model-emitted
server-owned fences with those canonical blocks.

This deliberately keeps the legacy fenced representation in persisted message
text. Older clients continue to render it, while the server—not a particular
LLM's formatting compliance—owns the bytes inside the fences.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.math_tools import VerifiedMathBlock


_SERVER_OWNED_FENCE_RE = re.compile(
    r"```(?:answer|result|final|graph|geometry)\b[^\n]*\n[\s\S]*?```",
    re.IGNORECASE,
)
_SERVER_OWNED_UNCLOSED_TAIL_RE = re.compile(
    r"```(?:answer|result|final|graph|geometry)\b[^\n]*\n[\s\S]*\Z",
    re.IGNORECASE,
)
_GRAPH_TYPES = {"function", "vertical", "number_line", "trajectory"}
_INSTALLED = False


def _canonical_answer(verified: VerifiedMathBlock) -> str | None:
    answer = getattr(verified, "canonical_answer", None)
    if isinstance(answer, str) and answer.strip():
        return answer.strip()

    fence = getattr(verified, "canonical_fence", None)
    if isinstance(fence, dict) and fence.get("type") == "answer":
        content = fence.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


def _canonical_diagrams(verified: VerifiedMathBlock) -> list[dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    many = getattr(verified, "canonical_fences", None)
    if isinstance(many, list):
        raw.extend(item for item in many if isinstance(item, dict))

    primary = getattr(verified, "canonical_fence", None)
    if isinstance(primary, dict) and primary.get("type") != "answer":
        raw.append(primary)

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if item.get("type") == "answer":
            continue
        key = json.dumps(item, sort_keys=True, separators=(",", ":"), default=str)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _diagram_kind(spec: dict[str, Any]) -> str:
    kind = str(spec.get("type") or "").strip().lower()
    if kind in _GRAPH_TYPES or "points" in spec or "expr" in spec:
        return "graph"
    return "geometry"


def _canonical_blocks(verified: VerifiedMathBlock) -> list[str]:
    blocks: list[str] = []
    for spec in _canonical_diagrams(verified):
        kind = _diagram_kind(spec)
        body = json.dumps(spec, separators=(",", ":"), ensure_ascii=False, default=str)
        blocks.append(f"```{kind}\n{body}\n```")

    # Keep the final answer last. This preserves the existing solver UX while
    # making the actual answer independent of model compliance.
    answer = _canonical_answer(verified)
    if answer:
        blocks.append(f"```answer\n{answer}\n```")
    return blocks


def enforce_verified_output_contract(
    content: str,
    verified: VerifiedMathBlock | None,
) -> str:
    """Return deterministic final text for a verified math/physics turn.

    If the verifier has canonical UI blocks, all model-emitted answer/graph/
    geometry fences are discarded and canonical server-owned blocks are
    appended once. Normal Markdown, inline/display math, code, and prose are
    left untouched. Turns without canonical blocks are unchanged.
    """
    if verified is None:
        return content

    blocks = _canonical_blocks(verified)
    if not blocks:
        return content

    cleaned = _SERVER_OWNED_FENCE_RE.sub("", content)
    # Also remove a model fence truncated at EOS. Without this, the canonical
    # block would be appended inside an open code fence and render as raw JSON.
    cleaned = _SERVER_OWNED_UNCLOSED_TAIL_RE.sub("", cleaned).strip()
    suffix = "\n\n".join(blocks)

    if not cleaned:
        return suffix
    return f"{cleaned}\n\n{suffix}"


def install_verified_output_contract() -> None:
    """Install the deterministic contract at the existing math-fence seam.

    Chat streaming already routes final math cleanup through
    ``math_fence.validate_math_fences_worker``. Wrapping that seam lets the
    backend own verified blocks without changing the WS/SSE protocol or old
    clients. The existing validator still runs afterwards, so graph densifying
    and legacy recovery remain intact.
    """
    global _INSTALLED
    if _INSTALLED:
        return

    from app.services import math_fence

    original_worker = math_fence.validate_math_fences_worker

    def deterministic_worker(content: str, verified: VerifiedMathBlock | None = None) -> str:
        canonicalized = enforce_verified_output_contract(content, verified)
        return original_worker(canonicalized, verified)

    math_fence.validate_math_fences_worker = deterministic_worker
    _INSTALLED = True
