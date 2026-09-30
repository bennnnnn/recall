"""Post-stream chemistry fences.

A verified chemistry turn replaces model answer, scene, and structure
fences with the solver's copies before any math rewrite. SMILES
enrichment runs after that, on whatever ```smiles fences remain, and
must not raise into the stream.
"""

from __future__ import annotations

import json
import logging
import re

from app.models.schemas.chemistry.scene import dump_scene
from app.modules import chemistry as chemistry_service
from app.modules.chemistry.block import VerifiedChemistry
from app.modules.chemistry.notation import typeset, typeset_json
from app.services.md_fence_scan import close_unclosed_fences, map_closed_fences, strip_closed_fences

logger = logging.getLogger(__name__)

_SMILES_PREFIX = re.compile(r"^smiles\s*:\s*", re.IGNORECASE)
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
        raw = _SMILES_PREFIX.sub("", lines[idx], count=1).strip()
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
    last = _SMILES_PREFIX.sub("", lines[-1], count=1).strip()
    if not last or len(last) > 500:
        return None, ""
    caption = "\n".join(lines[:-1]).strip()
    return last, caption


_UNRENDERABLE = "*Could not render that structure.*\n"


def _smiles_fence(smiles: str, caption: str = "") -> str:
    """One ```smiles fence: an optional caption line, then the SMILES."""
    body = f"{caption}\n{smiles}" if caption else smiles
    return f"```smiles\n{body}\n```"


def _read_fence(body: str) -> tuple[chemistry_service.MoleculeProperties | None, str]:
    """The validated molecule in a fence body and its caption; None when it cannot be read."""
    smiles, caption = _extract_smiles_from_fence(body)
    if smiles is None:
        return None, caption
    try:
        props = chemistry_service.validate_smiles(smiles)
    except Exception:
        logger.info("chemistry fence validation failed for %r", smiles, exc_info=True)
        return None, caption
    if not props.valid:
        logger.info("replacing invalid SMILES fence: %r", smiles)
        return None, caption
    return props, caption


def _canonicalize_smiles_fence(body: str) -> str:
    """Validate and rewrite a fence body. Never generate 3D."""
    if _extract_smiles_from_fence(body)[0] is None:
        return f"```smiles\n{body}```\n"  # nothing to validate: leave the fence as written
    props, caption = _read_fence(body)
    if props is None:
        return _UNRENDERABLE
    if not caption and props.formula and props.molecular_weight > 0:
        caption = f"{typeset(props.formula)} · {props.molecular_weight:.2f} g/mol"
    return _smiles_fence(props.smiles, caption) + "\n"


def _attach_molecule3d(body: str) -> tuple[str, bool]:
    """Return (```smiles fence + optional molecule3d, whether 3D was attached)."""
    props, caption = _read_fence(body)
    if props is None:
        return f"```smiles\n{body}```\n", False
    smiles_fence = _smiles_fence(props.smiles, caption)
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


# First line of a server ```answer fence whose body is chemistry text, not LaTeX.
CHEMISTRY_ANSWER_NOTATION = "notation: chemistry"

# Fences the solver owns on a verified chemistry turn. A model copy is removed
# and replaced from ChemistryResult so algebra finalization never rewrites it.
_OWNED_FENCE_LANGS = (
    "answer",
    "result",
    "final",
    "chem_scene",
    "smiles",
    "chemistry",
    "molecule",
    "molecule3d",
    "mol3d",
    "3dmol",
)


def format_chemistry_answer_fence(answer: str, *, verbatim: bool = False) -> str:
    """Answer fence the math renderer must not typeset as algebra.

    The answer is ASCII from the solver; the reader sees it typeset (H₂O, Fe²⁺, →) unless
    it carries SMILES or atom labels.
    """
    body = answer.strip() if verbatim else typeset(answer.strip())
    return f"```answer\n{CHEMISTRY_ANSWER_NOTATION}\n{body}\n```"


def _solver_fences(verified: VerifiedChemistry) -> list[str]:
    result = verified.result
    fences: list[str] = []
    answer = result.answer.strip()
    if answer:
        fences.append(format_chemistry_answer_fence(answer, verbatim=result.verbatim))
    if result.scene is not None:
        scene = dump_scene(result.scene)
        payload = json.dumps(scene if result.verbatim else typeset_json(scene), ensure_ascii=False)
        fences.append(f"```chem_scene\n{payload}\n```")
    smiles = (result.structure_smiles or "").strip()
    if smiles:
        fences.append(_smiles_fence(smiles))
    return fences


def _strip_owned_fences(content: str) -> str:
    cleaned = content
    for language in _OWNED_FENCE_LANGS:
        cleaned = strip_closed_fences(cleaned, language)
    return cleaned.strip()


def assemble_chemistry_reply(prose: str, verified: VerifiedChemistry) -> str:
    """Prose plus the solver's answer, scene, and structure. One blank line between."""
    parts = [prose.strip(), *_solver_fences(verified)]
    body = "\n\n".join(part for part in parts if part).strip()
    return f"{body}\n" if body else ""


def validate_chemistry_fences(content: str, verified: object | None = None) -> str:
    """Drop model answer/scene/structure fences and append the solver's copies."""
    if not isinstance(verified, VerifiedChemistry):
        return content
    # An unclosed model fence would swallow the solver fences appended below it.
    return assemble_chemistry_reply(_strip_owned_fences(close_unclosed_fences(content)), verified)


def replace_unclosed_chemistry_fences_safe(content: str, verified: object | None) -> str:
    """Chemistry-owned fallback. Never hand the turn to math graph recovery."""
    closed = close_unclosed_fences(content)
    try:
        return validate_chemistry_fences(closed, verified=verified)
    except Exception:
        logger.exception("chemistry fence recovery failed")
        cleaned = _strip_owned_fences(closed)
        if isinstance(verified, VerifiedChemistry) and verified.result.answer.strip():
            answer = format_chemistry_answer_fence(
                verified.result.answer, verbatim=verified.result.verbatim
            )
            parts = [cleaned, answer]
            body = "\n\n".join(part for part in parts if part).strip()
            return f"{body}\n" if body else ""
        return cleaned
