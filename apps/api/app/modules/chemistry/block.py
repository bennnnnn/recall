"""Verified chemistry prompt and direct-reply representation."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.models.schemas.chemistry import ChemistryIntent
from app.modules.chemistry.solvers import ChemistryResult, solve_chemistry
from app.services.solving import MathServiceError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerifiedChemistry:
    intent: ChemistryIntent
    result: ChemistryResult
    prompt_text: str


def _prompt_text(result: ChemistryResult) -> str:
    given = "\n".join(f"- {item}" for item in result.given)
    substitution = "\n".join(f"- {item}" for item in result.substitution)
    return (
        f"[{result.title}]\n"
        "Required visible layout: Given, Find, Formula, Substitution, Answer. "
        "Each heading and equation must be on its own line. Do not write a prose wall, "
        "do not recalculate, and do not add trailing zeros to verified numbers.\n"
        f"Given:\n{given}\n"
        f"Find:\n- {result.find}\n"
        f"Formula ({result.formula_name}):\n- {result.formula}\n"
        f"Substitution:\n{substitution}\n"
        f"Verified answer:\n- {result.answer}\n"
        "Use the verified answer verbatim."
    )


def build_verified_chemistry(intent: ChemistryIntent) -> VerifiedChemistry | None:
    try:
        result = solve_chemistry(intent)
    except MathServiceError as exc:
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
    return VerifiedChemistry(intent=intent, result=result, prompt_text=_prompt_text(result))


def verified_iupac(smiles: str, iupac_name: str) -> VerifiedChemistry:
    """A PubChem IUPACName that was actually returned. Not a local guess."""
    intent = ChemistryIntent(kind="organic", chemistry_op="iupac_name", formula=smiles)
    result = ChemistryResult(
        title="Verified IUPAC name",
        given=(smiles,),
        find="IUPAC name",
        formula_name="PubChem IUPACName",
        formula="the IUPACName property for this SMILES",
        substitution=(iupac_name,),
        answer=iupac_name,
        answer_value=iupac_name,
    )
    return VerifiedChemistry(intent=intent, result=result, prompt_text=_prompt_text(result))
