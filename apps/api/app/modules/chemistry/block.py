"""Verified chemistry prompt and direct-reply representation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.solvers import ChemistryResult, solve_chemistry
from app.modules.chemistry.solvers.common_chem import verified
from app.services.solving import SolveServiceError, VerifiedSolveBlock

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class VerifiedChemistry(VerifiedSolveBlock):
    """Chemistry verified result on the same transport math and physics use."""

    subject: Literal["chemistry"] = "chemistry"
    intent: ChemistryIntent
    result: ChemistryResult

    @property
    def prompt_text(self) -> str:
        return self.text


def _bullet_rows(text: str) -> str:
    """One bullet per line. Chemistry rows are text, so the math splitter (which cuts at every
    ``=`` and comma) is not used: it turned ``x = 0.6`` / ``[N2O4] = 0.4`` into fragments."""
    return "\n".join(f"- {line.strip()}" for line in text.splitlines() if line.strip())


def _prompt_text(result: ChemistryResult) -> str:
    given = "\n".join(f"- {item}" for item in result.given)
    substitution = "\n".join(_bullet_rows(item) for item in result.substitution)
    return (
        f"[{result.title}]\n"
        "Required visible layout: Given, Find, Formula, Substitution, Answer. "
        "Each heading and equation must be on its own line. Do not write a prose wall, "
        "do not recalculate, and do not add trailing zeros to verified numbers.\n"
        f"Given:\n{given}\n"
        f"Find:\n- {result.find}\n"
        f"Formula ({result.formula_name}):\n{_bullet_rows(result.formula)}\n"
        f"Substitution:\n{substitution}\n"
        f"Verified answer:\n{_bullet_rows(result.answer)}\n"
        "Use the verified answer verbatim. Do not emit answer, smiles, or chem_scene fences."
    )


def build_verified_chemistry(intent: ChemistryIntent) -> VerifiedChemistry | None:
    try:
        result = solve_chemistry(intent)
    except SolveServiceError as exc:
        logger.info(
            "chemistry verification skipped kind=%s op=%s reason=%s",
            intent.kind,
            intent.chemistry_op,
            exc,
        )
        return None
    except Exception:
        logger.warning(
            "chemistry verification failed kind=%s op=%s",
            intent.kind,
            intent.chemistry_op,
            exc_info=True,
        )
        return None
    return VerifiedChemistry(
        text=_prompt_text(result),
        intent=intent,
        result=result,
        canonical_answer=result.answer.strip(),
    )


def verified_iupac(smiles: str, iupac_name: str) -> VerifiedChemistry:
    """A PubChem IUPACName that was actually returned. Not a local guess."""
    intent = ChemistryIntent(kind="organic", chemistry_op="iupac_name", formula=smiles)
    result = verified(
        "Verified IUPAC name",
        (smiles,),
        "IUPAC name",
        "PubChem IUPACName",
        "the IUPACName property for this SMILES",
        (iupac_name,),
        iupac_name,
        iupac_name,
        verbatim=True,
    )
    return VerifiedChemistry(
        text=_prompt_text(result),
        intent=intent,
        result=result,
        canonical_answer=result.answer.strip(),
    )
