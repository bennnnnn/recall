"""Post-stream chemistry fence enrichment.

Validates SMILES fences in the assistant's output using RDKit and
enriches them with verified molecular properties (formula, weight,
atom count). Invalid SMILES are stripped so the mobile renderer
doesn't show a broken molecule card.

This runs AFTER validate_math_fences (which handles geometry/graph/
answer fences) and BEFORE the text is persisted. It must be fast
and never raise into the stream — failures are logged and the raw
text is kept.
"""

from __future__ import annotations

import logging
import re

from app.services import chemistry as chemistry_service

logger = logging.getLogger(__name__)

# ```smiles or ```chemistry fence — captures the body (non-greedy).
_SMILES_FENCE_RE = re.compile(
    r"```(?:smiles|chemistry)\s*\n([\s\S]*?)```",
    re.IGNORECASE,
)
# Limit how many fences we process to bound the work.
_MAX_SMILES_FENCES = 20


def _extract_smiles_from_fence(body: str) -> str | None:
    """Extract the SMILES line from a fence body (last non-empty, non-comment line)."""
    lines = [line.strip() for line in body.split("\n") if line.strip() and not line.startswith("#")]
    if not lines:
        return None
    # The SMILES is the last line (caption may precede it).
    raw = lines[-1].replace("smiles:", "", 1).strip()
    if not raw or len(raw) > 500:
        return None
    return raw


def enrich_chemistry_fences(content: str) -> str:
    """Validate and enrich all ```smiles fences in the content.

    - Valid SMILES: replace with canonical SMILES (RDKit-normalized) and
      append a ```molecule3d fence with a 3D SDF for interactive viewing.
    - Invalid SMILES: strip the fence entirely (the renderer would show
      a broken card).

    This is synchronous (RDKit is C-bound and fast for small molecules).
    The caller should run it in the process pool if latency matters.
    """
    count = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        if count > _MAX_SMILES_FENCES:
            return match.group(0)  # stop processing beyond the limit
        body = match.group(1)
        smiles = _extract_smiles_from_fence(body)
        if smiles is None:
            return match.group(0)  # leave as-is if we can't parse
        try:
            props = chemistry_service.validate_smiles(smiles)
        except Exception:
            logger.info("chemistry fence validation failed for %r", smiles, exc_info=True)
            return match.group(0)
        if not props.valid:
            # Strip invalid SMILES fence so the renderer doesn't show a
            # broken molecule card.
            logger.info("stripping invalid SMILES fence: %r", smiles)
            return ""
        # Replace with canonical SMILES (RDKit-normalized). Keep any
        # caption lines from the original fence.
        lines = [line for line in body.split("\n") if line.strip() and not line.startswith("#")]
        # Drop the last line (the old SMILES) and re-append canonical.
        caption_lines = lines[:-1] if len(lines) > 1 else []
        caption = "\n".join(caption_lines).strip()
        # If no caption was provided, synthesize one with verified properties
        # (formula + MW) so the mobile card surfaces the verified data.
        if not caption and props.formula and props.molecular_weight > 0:
            caption = f"{props.formula} · {props.molecular_weight:.2f} g/mol"
        if caption:
            smiles_fence = f"```smiles\n{caption}\n{props.smiles}\n```"
        else:
            smiles_fence = f"```smiles\n{props.smiles}\n```"

        # Generate a 3D SDF for the molecule3d fence (best-effort —
        # skip if 3D embedding fails for complex molecules).
        mol3d_fence = ""
        try:
            coords = chemistry_service.generate_3d_coordinates(props.smiles)
            if coords.sdf:
                # Caption after M END — never prepend it. An extra line before
                # the RDKit molblock shifts the V2000 counts off line 4 and
                # 3Dmol.js parses 0 atoms (blank viewer).
                title = props.formula or caption or "Molecule"
                mol3d_fence = f"\n```molecule3d\n{coords.sdf.rstrip()}\n{title}\n```"
        except Exception:
            logger.info("3D SDF generation failed for %r", props.smiles, exc_info=True)

        return smiles_fence + mol3d_fence

    return _SMILES_FENCE_RE.sub(_replace, content)


def enrich_chemistry_fences_worker(content: str) -> str:
    """Picklable entry for the process pool (positional args only)."""
    return enrich_chemistry_fences(content)
