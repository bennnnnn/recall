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

from app.services import chemistry as chemistry_service
from app.services.md_fence_scan import map_closed_fences

logger = logging.getLogger(__name__)

# Limit how many fences we process to bound the work.
_MAX_SMILES_FENCES = 20
# 3D embed is expensive; validate all fences first, then attach 3D to a few.
_MAX_3D_FENCES = 2


def _candidate_lines(body: str) -> list[str]:
    return [
        line.strip()
        for line in body.split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]


def _extract_smiles_from_fence(body: str) -> tuple[str | None, str]:
    """Pick a SMILES line from the bottom (mobile's parseChemistryFence).

    Returns ``(smiles, caption)``. Caption is every other non-comment line.
    If nothing validates, the last line is still returned so the caller can
    fail-closed.
    """
    lines = _candidate_lines(body)
    if not lines:
        return None, ""
    for idx in range(len(lines) - 1, -1, -1):
        raw = lines[idx].replace("smiles:", "", 1).strip()
        if not raw or len(raw) > 500:
            continue
        try:
            props = chemistry_service.validate_smiles(raw)
        except Exception:
            logger.info("chemistry fence line validation failed for %r", raw, exc_info=True)
            continue
        if props.valid:
            caption = "\n".join(lines[:idx] + lines[idx + 1 :]).strip()
            return raw, caption
    last = lines[-1].replace("smiles:", "", 1).strip()
    if not last or len(last) > 500:
        return None, ""
    caption = "\n".join(lines[:-1]).strip()
    return last, caption


def _canonicalize_smiles_fence(body: str) -> str:
    """Validate and rewrite a fence body. Never generate 3D."""
    smiles, caption = _extract_smiles_from_fence(body)
    if smiles is None:
        return f"```smiles\n{body}```\n"
    try:
        props = chemistry_service.validate_smiles(smiles)
    except Exception:
        logger.info("chemistry fence validation failed for %r", smiles, exc_info=True)
        return "*Could not render that structure.*\n"
    if not props.valid:
        logger.info("replacing invalid SMILES fence: %r", smiles)
        return "*Could not render that structure.*\n"
    if not caption and props.formula and props.molecular_weight > 0:
        caption = f"{props.formula} · {props.molecular_weight:.2f} g/mol"
    if caption:
        return f"```smiles\n{caption}\n{props.smiles}\n```\n"
    return f"```smiles\n{props.smiles}\n```\n"


def _attach_molecule3d(body: str) -> tuple[str, bool]:
    """Return (```smiles fence + optional molecule3d, whether 3D was attached)."""
    smiles, caption = _extract_smiles_from_fence(body)
    if smiles is None:
        return f"```smiles\n{body}```\n", False
    try:
        props = chemistry_service.validate_smiles(smiles)
    except Exception:
        logger.info("chemistry fence validation failed for %r", smiles, exc_info=True)
        return "*Could not render that structure.*\n", False
    if not props.valid:
        return f"```smiles\n{body}```\n", False
    if caption:
        smiles_fence = f"```smiles\n{caption}\n{props.smiles}\n```"
    else:
        smiles_fence = f"```smiles\n{props.smiles}\n```"
    try:
        coords = chemistry_service.generate_3d_coordinates(props.smiles)
        if coords.sdf:
            title = props.formula or caption or "Molecule"
            mol3d_fence = f"\n```molecule3d\n{coords.sdf.rstrip()}\n{title}\n```\n"
            return smiles_fence + mol3d_fence, True
    except Exception:
        logger.info("3D SDF generation failed for %r", props.smiles, exc_info=True)
    return smiles_fence + "\n", False


def enrich_chemistry_fences(content: str) -> str:
    """Validate and enrich all ```smiles / ```chemistry fences.

    Closed fences only (bare-backtick closer). Invalid SMILES become an
    italic note. Every closed fence is validated first; 3D SDF is attached
    only for the first ``_MAX_3D_FENCES`` valid molecules so one slow embed
    cannot skip stripping later invalid fences.
    """
    content = map_closed_fences(
        content,
        "smiles",
        _canonicalize_smiles_fence,
        max_count=_MAX_SMILES_FENCES,
    )
    content = map_closed_fences(
        content,
        "chemistry",
        _canonicalize_smiles_fence,
        max_count=_MAX_SMILES_FENCES,
    )
    mol3d_left = _MAX_3D_FENCES

    def _attach(body: str) -> str:
        nonlocal mol3d_left
        if mol3d_left <= 0:
            return f"```smiles\n{body.rstrip()}\n```\n"
        rewritten, used_3d = _attach_molecule3d(body)
        if used_3d:
            mol3d_left -= 1
        return rewritten

    return map_closed_fences(
        content,
        "smiles",
        _attach,
        max_count=_MAX_SMILES_FENCES,
    )


def enrich_chemistry_fences_worker(content: str) -> str:
    """Picklable entry for the process pool (positional args only)."""
    return enrich_chemistry_fences(content)
