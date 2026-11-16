"""The structure of the compound a chemistry question is about, drawn without being asked.

The owner (2026-11-15): a student need not ask to see a molecule; when its structure helps
teach the question, it is drawn. "Show me the structure of caffeine" is the solve's
(``block.verified_structure``); this is every other question about one molecular compound
("What is ibuprofen?", "Why does ethanol dissolve in water?", "the molar mass of glucose").

One short structured call names the compound, exactly as the user wrote it, or nothing. The
name must be in the user's words; PubChem gives its structure, RDKit holds it to one valid
molecule, and the server draws it under the reply (``chat.figure_turn``). A salt, a
mixture, a lone atom, no read, or no record: nothing is drawn, and the reply stands.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Sequence

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.models.routing_lanes import ROUTING
from app.services.solving import VerifiedSolveBlock
from app.services.text_normalize import collapse_ws

logger = logging.getLogger(__name__)

_MAX_TOKENS = 60
_MAX_CHARS = 1200
_EARLIER_CHARS = 600
# A molecule with fewer atoms other than hydrogen is one letter on the screen ("C", "O").
_MIN_HEAVY_ATOMS = 2

_PROMPT = (
    "The user did not ask for a picture. Name the one compound this chemistry question is "
    "about when a drawing of its structure helps a student: a molecule with bonds to draw, "
    "such as an organic compound, a drug, a sugar, an acid like acetic acid, or a covalent "
    "molecule like carbon dioxide. Copy the words the user writes for it, exactly "
    '("ibuprofen", "acetic acid"): a formula only when the user writes one ("C2H5OH"), '
    "never a name or formula of your own.\n"
    'Give "" when the question names no compound or several, a reaction or equation, only '
    "an element, an ion or an atom, a salt such as sodium chloride, a mixture or a "
    "solution's strength (pH, molarity, dilution), a gas law, or a lab or safety question. "
    "A question about one named molecular compound, its uses, properties, mass or how it "
    "works, names it: when in doubt, name it.\n"
    'Examples: "How does paracetamol work?" -> {"name": "paracetamol"}; "Is glycerol '
    'soluble in water?" -> {"name": "glycerol"}; "What is the molar mass of sucrose?" -> '
    '{"name": "sucrose"}; "What is the pH of 0.2 M NaOH?" -> {"name": ""}; "Balance '
    'Fe + O2 -> Fe2O3" -> {"name": ""}.\n'
    'Return JSON: {"name": "..."}'
)


class CompoundRead(BaseModel):
    name: str = Field(default="", max_length=80)


def _message(question: str, earlier: Sequence[str]) -> str:
    before = [text[:_EARLIER_CHARS] for text in earlier if text.strip()]
    if not before:
        return question[:_MAX_CHARS]
    joined = "\n".join(f"- {text}" for text in before)
    return f"Earlier user messages:\n{joined}\n\nLast message: {question[:_MAX_CHARS]}"


def written_by_user(name: str, texts: Sequence[str]) -> bool:
    """The name is in the user's own words, as a whole word or phrase."""
    wanted = collapse_ws(name).casefold()
    if not wanted:
        return False
    pattern = re.compile(rf"(?<![\w-]){re.escape(wanted)}(?![\w-])")
    return any(pattern.search(collapse_ws(text).casefold()) for text in texts)


async def read_compound(settings: Settings, question: str, earlier: Sequence[str]) -> str | None:
    """The compound the question is about, as the user wrote it, or None."""
    from app.core.redis import get_redis_client
    from app.gateways.structured_completion import complete_structured
    from app.services import quota as quota_service

    try:
        if await quota_service.global_spend_exceeded(get_redis_client(), settings):
            return None
        read = await complete_structured(
            settings=settings,
            model_alias=ROUTING.compound_read,
            messages=[
                {"role": "system", "content": _PROMPT},
                {"role": "user", "content": _message(question, earlier)},
            ],
            schema=CompoundRead,
            max_tokens=_MAX_TOKENS,
            timeout_seconds=settings.figure_read_timeout_seconds,
            allow_fallback=False,
            quiet_timeout=True,
        )
    except Exception as exc:  # A read is a hint: any failure draws nothing.
        logger.info("compound read failed (%s)", type(exc).__name__)
        return None
    name = collapse_ws(read.name) if read is not None else ""
    return name or None


def structure_fence(smiles: str, name: str) -> str | None:
    """The ```smiles fence of one valid molecule, captioned with its name; None for a salt,
    a mixture, a lone atom or a structure RDKit cannot read. Runs in the SymPy pool."""
    from rdkit import Chem

    from app.modules.chemistry.smiles import drawing_smiles

    if not smiles or "." in smiles:
        return None
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None or molecule.GetNumHeavyAtoms() < _MIN_HEAVY_ATOMS:
        return None
    return f"```smiles\n{name}\n{drawing_smiles(smiles)}\n```"


async def pubchem_structure(name: str) -> str | None:
    from app.core.redis import get_redis_client
    from app.gateways import pubchem_gateway
    from app.modules.chemistry.context import PUBCHEM_BUDGET_SECONDS

    try:
        lookup = await asyncio.wait_for(
            pubchem_gateway.lookup_by_name(name, redis=get_redis_client()),
            PUBCHEM_BUDGET_SECONDS,
        )
    except Exception as exc:  # A timeout or an outage draws nothing.
        logger.info("compound not looked up: %s", type(exc).__name__)
        return None
    compound = lookup.compound
    if compound is None or lookup.error is not None:
        return None
    return compound.isomeric_smiles or compound.smiles


async def draw_structure(question: str, earlier: Sequence[str], settings: Settings) -> str | None:
    """The fence of the structure that helps teach the question, or None."""
    from app.core import sympy_executor

    if not (settings.chemistry_enabled and settings.teaching_figures_enabled):
        return None
    if not question.strip():
        return None
    name = await read_compound(settings, question, earlier)
    if name is None or not written_by_user(name, [question, *earlier]):
        return None
    smiles = await pubchem_structure(name)
    if smiles is None:
        return None
    try:
        return await sympy_executor.run_sympy(
            structure_fence, smiles, name, timeout=settings.stem_solve_timeout_seconds
        )
    except Exception as exc:  # A failed check draws nothing; the reply stands.
        logger.info("structure not drawn (%s)", type(exc).__name__)
        return None


def holds_a_structure(text: str) -> bool:
    """The reply already draws a molecule: no second one is added."""
    return any(f"```{lang}" in text for lang in ("smiles", "chemistry", "molecule3d"))


def solve_drew_a_structure(verified: VerifiedSolveBlock | None) -> bool:
    """The turn's solve drew the compound already ("show me the structure of caffeine")."""
    result = getattr(verified, "result", None)
    return bool(getattr(result, "structure_smiles", ""))
